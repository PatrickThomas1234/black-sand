"""Build #23 — Velocity-Frühindikator.

Projiziert die Endperformance frisch geposteter Posts aus ihrem bisherigen
Engagement + Alter — über eine generische Engagement-Reifekurve (welcher Anteil
des finalen Engagements ist bis Stunde X typischerweise erreicht).

So sieht man kurz nach dem Posten, ob ein Post auf Über- oder Unterperformance
zusteuert. Wird mit regelmäßigem `bs-refresh` (mehr frühe Messpunkte) präziser;
die Reifekurve lässt sich später aus echten Snapshot-Daten kalibrieren.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .analytics import profile_dataframe
from .scoring import _baseline, _rating

# Anteil des finalen Engagements, der bis Alter X (Stunden) typischerweise erreicht ist
_CURVE = [
    (0, 0.02), (1, 0.10), (3, 0.25), (6, 0.40), (12, 0.60),
    (24, 0.78), (48, 0.90), (72, 0.96), (96, 0.99), (1e9, 1.0),
]
MATURE_HOURS = 96  # ab hier gilt ein Post als „ausgereift" (kein Frühindikator mehr)


def _fraction(age_h: float) -> float:
    age_h = max(0.0, age_h)
    for (a0, f0), (a1, f1) in zip(_CURVE, _CURVE[1:]):
        if age_h <= a1:
            if a1 == a0:
                return f1
            return f0 + (f1 - f0) * (age_h - a0) / (a1 - a0)
    return 1.0


def early_indicator(username: str, platform: str | None = None,
                    max_age_days: float = 7.0) -> list[dict[str, Any]]:
    df = profile_dataframe(username, platform)
    if df.empty:
        return []
    df = df.dropna(subset=["posted_at", "engagement_rate"]).copy()
    if df.empty:
        return []

    now = datetime.now(timezone.utc)
    df["age_h"] = (now - df["posted_at"]).dt.total_seconds() / 3600

    # Baseline der FINALEN Engagement-Rate je Post-Typ (nur ausgereifte Posts)
    mature = df[df["age_h"] >= MATURE_HOURS]
    base: dict[str, tuple[float, float]] = {}
    for t, g in mature.groupby("post_type"):
        if len(g) >= 5:
            base[t] = _baseline(list(g["engagement_rate"]))
    global_base = _baseline(list(mature["engagement_rate"])) if not mature.empty else (0.0, 0.0)

    fresh = df[df["age_h"] <= max_age_days * 24].sort_values("age_h")
    rows = []
    for _, r in fresh.iterrows():
        age_h = float(r["age_h"])
        frac = _fraction(age_h)
        cur_er = float(r["engagement_rate"])
        proj_er = cur_er / frac if frac > 0 else cur_er
        mean, std = base.get(r["post_type"], global_base)
        proj_z = (proj_er - mean) / std if std > 0 else 0.0
        conf = "hoch" if age_h >= 48 else ("mittel" if age_h >= 12 else "niedrig")
        rows.append({
            "shortcode": r["shortcode"], "post_type": r["post_type"],
            "age_h": round(age_h, 1), "matured_pct": round(frac * 100),
            "current_er": round(cur_er, 2), "projected_er": round(proj_er, 2),
            "projected_rating": _rating(proj_z), "projected_z": round(proj_z, 2),
            "current_rating": r.get("rating"), "confidence": conf,
            "caption": (r.get("caption") or "")[:70],
        })
    return rows
