"""Build #20 — quantitatives ML-Prognosemodell.

Erkenntnis aus dem Backtesting: einfache Metadaten-Features (Länge, Hashtags,
Zeit) sagen den baseline-relativen Score NICHT zuverlässig voraus (CV-R²<0,
AUC≈0,47). Der echte Prädiktor ist der INHALT — über die semantischen Embeddings
(Caption+Transkript+Visual) lässt sich "guter Post (z≥0,5)" mit AUC≈0,63
vorhersagen.

Headline-Modell = LogisticRegression auf den Post-Embeddings → P(guter Post).
Die Metadaten-Feature-Importance bleibt als *richtungsweisende* Diagnose erhalten
(ehrlich gekennzeichnet: schwache Vorhersagekraft).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from .analytics import list_profiles, profile_dataframe
from .db import get_client

GOOD_THRESHOLD = 0.5  # algo_zscore ab dem ein Post als "gut+" gilt


# ---------------------------------------------------------------------------
# Headline-Modell: Embeddings → P(guter Post)
# ---------------------------------------------------------------------------
def _embedding_dataset() -> tuple[np.ndarray, np.ndarray]:
    db = get_client()
    emb = db.table("post_embeddings").select("post_id,embedding").execute().data
    sc = {s["post_id"]: s for s in
          db.table("performance_scores").select("post_id,algo_zscore").execute().data}
    X, y = [], []
    for e in emb:
        s = sc.get(e["post_id"])
        if not s or s.get("algo_zscore") is None:
            continue
        v = e["embedding"]
        if isinstance(v, str):
            v = [float(x) for x in v.strip("[]").split(",")]
        X.append(v)
        y.append(1 if float(s["algo_zscore"]) >= GOOD_THRESHOLD else 0)
    return np.array(X, dtype=float), np.array(y, dtype=int)


@lru_cache(maxsize=1)
def train_model() -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score

    X, y = _embedding_dataset()
    n = len(X)
    if n < 40 or len(set(y)) < 2:
        raise RuntimeError(f"Zu wenig/ungeeignete Daten ({n} Posts) für das Modell.")

    clf = LogisticRegression(max_iter=1000, C=0.5)
    clf.fit(X, y)
    cv_auc = None
    try:
        if y.sum() >= 10:
            cv_auc = round(float(cross_val_score(clf, X, y, cv=5, scoring="roc_auc").mean()), 3)
    except Exception:  # noqa: BLE001
        pass
    return {"clf": clf, "n": n, "cv_auc": cv_auc, "base_rate": round(float(y.mean()), 3)}


def predict_good(draft_text: str) -> dict[str, Any] | None:
    """P(guter Post) für einen Entwurf — über sein Content-Embedding."""
    try:
        from .embeddings import embed

        m = train_model()
        v = embed([draft_text])[0]
        p = float(m["clf"].predict_proba([v])[0][1])
        return {"prob_good": round(p, 3), "cv_auc": m["cv_auc"],
                "base_rate": m["base_rate"], "n": m["n"]}
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Diagnose: Metadaten-Feature-Importance (richtungsweisend, schwache Vorhersage)
# ---------------------------------------------------------------------------
_TZ = "Europe/Berlin"
_META_FEATURES = [
    "caption_length", "hashtag_count", "tagged_count", "is_video", "audio_original",
    "weekday", "hour", "has_question", "transcript_len", "has_visual",
    "type_reel", "type_carousel", "type_image", "type_video",
]


def _meta_dataframe() -> pd.DataFrame:
    frames = []
    for p in list_profiles():
        try:
            d = profile_dataframe(p["username"], p.get("platform"))
        except Exception:  # noqa: BLE001
            continue
        if not d.empty:
            frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def metadata_importances() -> dict[str, Any]:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import cross_val_score

    df = _meta_dataframe().dropna(subset=["zscore"]).copy()
    if len(df) < 30:
        return {"n": len(df), "cv_r2": None, "importances": []}
    local = df["posted_at"].dt.tz_convert(_TZ)
    f = pd.DataFrame(index=df.index)
    f["caption_length"] = pd.to_numeric(df.get("caption_length"), errors="coerce").fillna(0)
    f["hashtag_count"] = pd.to_numeric(df.get("hashtag_count"), errors="coerce").fillna(0)
    f["tagged_count"] = pd.to_numeric(df.get("tagged_count"), errors="coerce").fillna(0)
    f["is_video"] = df["is_video"].fillna(False).astype(int)
    f["audio_original"] = df["uses_original_audio"].map({True: 1, False: 0}).fillna(0).astype(int)
    f["weekday"] = local.dt.weekday.fillna(0).astype(int)
    f["hour"] = local.dt.hour.fillna(12).astype(int)
    f["has_question"] = df["caption"].fillna("").astype(str).str.contains(r"\?").astype(int)
    f["transcript_len"] = df["transcript"].fillna("").astype(str).str.len()
    f["has_visual"] = df["visual"].map(lambda v: 1 if isinstance(v, dict) else 0)
    for t in ("reel", "carousel", "image", "video"):
        f[f"type_{t}"] = (df["post_type"] == t).astype(int)
    X, y = f[_META_FEATURES], df["zscore"].astype(float)

    reg = GradientBoostingRegressor(random_state=0).fit(X, y)
    cv_r2 = None
    try:
        cv_r2 = round(float(cross_val_score(reg, X, y, cv=5, scoring="r2").mean()), 3)
    except Exception:  # noqa: BLE001
        pass
    imps = sorted(({"feature": c, "importance": round(float(i), 3)}
                   for c, i in zip(_META_FEATURES, reg.feature_importances_)),
                  key=lambda x: -x["importance"])
    return {"n": len(X), "cv_r2": cv_r2, "importances": imps}
