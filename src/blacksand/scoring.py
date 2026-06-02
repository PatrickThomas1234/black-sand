"""Phase 3 — Performance-Scoring.

Kernidee: Absolute Likes sagen wenig. Wir bewerten jeden Post **relativ zur
Baseline des eigenen Kanals** — und zwar segmentiert nach Post-Typ, weil Reels
und Carousels unterschiedliche Engagement-Dynamik haben.

Pro Post:
  engagement_rate = (likes + comments) / follower_count * 100   [%]
  z-Score         = (er - baseline_mean) / baseline_std
  rating          = Bucket über den z-Score

Baseline = Mittelwert/Std der engagement_rate aller Posts desselben Typs im
Kanal. Hat ein Typ < MIN_GROUP Posts, fällt er auf die Gesamt-Baseline zurück.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from .db import get_client

MIN_GROUP = 5  # ab so vielen Posts gilt eine typ-spezifische Baseline als belastbar


def _rating(z: float) -> str:
    if z >= 2.0:
        return "viral"
    if z >= 0.5:
        return "good"
    if z >= -0.5:
        return "avg"
    if z >= -1.5:
        return "below"
    return "flop"


def _baseline(values: list[float]) -> tuple[float, float]:
    """(mean, std) — std=0 wenn zu wenige/identische Werte."""
    if len(values) < 2:
        return (values[0] if values else 0.0), 0.0
    return statistics.mean(values), statistics.pstdev(values)


def score_profile(username: str, platform: str | None = None) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")

    q = db.table("profiles").select("id,username,follower_count").eq("username", username)
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB. Erst ingesten.")
    profile = prof[0]
    followers = profile["follower_count"] or 0
    if followers <= 0:
        raise RuntimeError("follower_count fehlt/0 — Engagement-Rate nicht berechenbar.")

    posts = (
        db.table("posts")
        .select("id,platform_post_id,post_type,caption")
        .eq("profile_id", profile["id"])
        .execute()
        .data
    )
    if not posts:
        return {"profile": username, "scored": 0}

    # Jüngsten Metrik-Snapshot pro Post holen
    ids = [p["id"] for p in posts]
    snaps = (
        db.table("metric_snapshots")
        .select("post_id,likes,comments,views,plays,captured_at")
        .in_("post_id", ids)
        .order("captured_at", desc=True)
        .execute()
        .data
    )
    latest: dict[str, dict[str, Any]] = {}
    for s in snaps:
        latest.setdefault(s["post_id"], s)

    # Engagement-Rate + View-Rate (Reichweite) pro Post
    for p in posts:
        m = latest.get(p["id"], {})
        likes = m.get("likes") or 0
        comments = m.get("comments") or 0
        p["_likes"], p["_comments"] = likes, comments
        p["_views"] = m.get("views")
        p["_er"] = (likes + comments) / followers * 100
        # Reichweite: wie weit über die Follower-Basis hinaus ausgespielt (nur Videos)
        p["_vr"] = (p["_views"] / followers * 100) if p["_views"] else None

    # Engagement-Baselines: pro Typ + global
    global_er = [p["_er"] for p in posts]
    global_base = _baseline(global_er)
    by_type: dict[str, list[float]] = {}
    for p in posts:
        by_type.setdefault(p["post_type"] or "other", []).append(p["_er"])
    type_base = {t: _baseline(v) for t, v in by_type.items()}

    # View-Baseline: über alle Posts mit Views (i.d.R. Videos/Reels)
    view_vals = [p["_vr"] for p in posts if p["_vr"] is not None]
    view_base = _baseline(view_vals) if len(view_vals) >= MIN_GROUP else None

    # Scoren + speichern
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for p in posts:
        t = p["post_type"] or "other"
        use_type = len(by_type[t]) >= MIN_GROUP
        mean, std = type_base[t] if use_type else global_base
        eng_z = (p["_er"] - mean) / std if std > 0 else 0.0

        # View-z (Reichweite) nur wenn Views + belastbare Baseline
        view_z = None
        if p["_vr"] is not None and view_base and view_base[1] > 0:
            view_z = (p["_vr"] - view_base[0]) / view_base[1]

        # Algo-Score: bei Videos Mittel aus Engagement- und Reichweiten-z, sonst nur Engagement
        algo_z = (eng_z + view_z) / 2 if view_z is not None else eng_z

        rows.append(
            {
                "post_id": p["id"],
                "engagement_rate": round(p["_er"], 4),
                "baseline_zscore": round(eng_z, 4),
                "view_rate": round(p["_vr"], 4) if p["_vr"] is not None else None,
                "view_zscore": round(view_z, 4) if view_z is not None else None,
                "algo_zscore": round(algo_z, 4),
                "rating": _rating(algo_z),
                "computed_at": now,
                "details": {
                    "likes": p["_likes"],
                    "comments": p["_comments"],
                    "views": p["_views"],
                    "followers": followers,
                    "baseline_scope": t if use_type else "global",
                    "baseline_mean": round(mean, 4),
                    "baseline_std": round(std, 4),
                    "n": len(by_type[t]) if use_type else len(posts),
                },
            }
        )

    # Frische Scores: alte für diese Posts löschen, dann neu einfügen
    db.table("performance_scores").delete().in_("post_id", ids).execute()
    db.table("performance_scores").insert(rows).execute()

    # Für die CLI-Ausgabe anreichern
    for p, r in zip(posts, rows):
        r["_caption"] = (p["caption"] or "")[:50].replace("\n", " ")
        r["_post_type"] = p["post_type"]
    return {"profile": username, "scored": len(rows), "rows": rows}
