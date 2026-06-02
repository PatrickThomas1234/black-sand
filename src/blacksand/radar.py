"""Build #27a — Trend-Radar.

Erkennt über die gesamte Nische (eigener Account + Konkurrenten), WAS gerade
aufsteigt: Hashtags & Formate mit positivem Engagement-Momentum (jüngste Periode
vs. davor) und Accounts, die gerade zulegen. Ziel: Trends früh adaptieren.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .db import get_client
from .niche_intel import niche_usernames


def _niche_posts_df(username: str, platform: str | None) -> pd.DataFrame:
    db = get_client()
    me, comps = niche_usernames(username, platform)
    profs = (
        db.table("profiles").select("id,username")
        .in_("username", [me, *comps]).execute().data
    )
    pid2user = {p["id"]: p["username"] for p in profs}
    if not pid2user:
        return pd.DataFrame()
    posts = (
        db.table("posts").select("id,profile_id,post_type,posted_at,hashtags")
        .in_("profile_id", list(pid2user)).execute().data
    )
    if not posts:
        return pd.DataFrame()
    ids = [p["id"] for p in posts]
    sc = {s["post_id"]: s.get("engagement_rate")
          for s in db.table("performance_scores").select("post_id,engagement_rate")
          .in_("post_id", ids).execute().data}
    rows = [{
        "account": pid2user.get(p["profile_id"]),
        "post_type": p["post_type"],
        "posted_at": p["posted_at"],
        "hashtags": [h.lower() for h in (p.get("hashtags") or [])],
        "er": sc.get(p["id"]),
    } for p in posts]
    df = pd.DataFrame(rows)
    df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, errors="coerce")
    return df.dropna(subset=["posted_at"])


def _arrow(recent: float, older: float | None) -> str:
    if older is None:
        return "🆕"
    if recent > older * 1.15:
        return "↑"
    if recent < older * 0.85:
        return "↓"
    return "→"


def niche_radar(username: str, platform: str | None = None,
                recent_days: int = 45, min_recent: int = 3) -> dict[str, Any]:
    df = _niche_posts_df(username, platform)
    if df.empty:
        return {}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=recent_days)
    df["recent"] = df["posted_at"] >= cutoff

    # --- Hashtags ---
    ex = df.explode("hashtags").dropna(subset=["hashtags", "er"])
    hot_tags = []
    for tag, g in ex.groupby("hashtags"):
        rec = g[g["recent"]]
        old = g[~g["recent"]]
        if len(rec) < min_recent:
            continue
        rec_er = float(rec["er"].mean())
        old_er = float(old["er"].mean()) if len(old) else None
        hot_tags.append({
            "hashtag": tag, "recent_n": int(len(rec)),
            "recent_er": round(rec_er, 2),
            "older_er": round(old_er, 2) if old_er is not None else None,
            "trend": _arrow(rec_er, old_er),
        })
    hot_tags.sort(key=lambda x: -x["recent_er"])

    # --- Formate ---
    hot_formats = []
    for t, g in df.dropna(subset=["er"]).groupby("post_type"):
        rec = g[g["recent"]]
        old = g[~g["recent"]]
        if rec.empty:
            continue
        rec_er = float(rec["er"].mean())
        old_er = float(old["er"].mean()) if len(old) else None
        hot_formats.append({
            "format": t, "recent_n": int(len(rec)), "recent_er": round(rec_er, 2),
            "older_er": round(old_er, 2) if old_er is not None else None,
            "trend": _arrow(rec_er, old_er),
        })
    hot_formats.sort(key=lambda x: -x["recent_er"])

    # --- Surging Accounts ---
    surging = []
    for acc, g in df.dropna(subset=["er"]).groupby("account"):
        rec = g[g["recent"]]
        old = g[~g["recent"]]
        if len(rec) < min_recent or old.empty:
            continue
        rec_er, old_er = float(rec["er"].mean()), float(old["er"].mean())
        if old_er > 0:
            surging.append({
                "account": acc, "recent_er": round(rec_er, 2), "older_er": round(old_er, 2),
                "change_pct": round((rec_er / old_er - 1) * 100),
            })
    surging.sort(key=lambda x: -x["change_pct"])

    return {
        "recent_days": recent_days,
        "n_recent": int(df["recent"].sum()),
        "hot_hashtags": hot_tags[:12],
        "hot_formats": hot_formats,
        "surging_accounts": surging[:8],
    }
