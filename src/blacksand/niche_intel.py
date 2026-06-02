"""Build #2 — Nische-Intelligenz + Gap-Analyse.

Aggregiert über den eigenen Account UND seine Konkurrenten, wie in dieser Nische
erfolgreich gepostet wird (Engagement-Rate nach Format/Zeit/Hashtags, Top-Posts),
und lässt Claude daraus ableiten: „so gewinnt die Nische" + eine konkrete
GAP-ANALYSE „das solltest genau DU adaptieren".

Cross-Account wird über die Engagement-Rate verglichen (nicht über den
profil-internen z-Score, der nur innerhalb eines Accounts vergleichbar ist).
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .analytics import feature_aggregates, profile_dataframe
from .competitors import latest_competitors
from .config import get_settings
from .db import get_client
from .llm import tool_call

_LOCAL_TZ = "Europe/Berlin"
_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def niche_usernames(username: str, platform: str | None = None) -> tuple[str, list[str]]:
    comp = latest_competitors(username, platform)
    ing = comp["payload"].get("ingested", []) if comp else []
    return username, ing


def niche_dataframe(username: str, platform: str | None = None) -> pd.DataFrame:
    me, comp = niche_usernames(username, platform)
    frames = []
    for u in [me, *comp]:
        # Eigener Account plattform-spezifisch; Konkurrenten sind eindeutige Handles
        d = profile_dataframe(u, platform if u == me else None)
        if not d.empty:
            d = d.copy()
            d["account"] = u
            d["is_own"] = (u == me)
            frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _er_by(df: pd.DataFrame, col: str) -> list[dict]:
    g = (
        df.dropna(subset=["engagement_rate"])
        .groupby(col, dropna=True)
        .agg(n=("engagement_rate", "size"), avg_er=("engagement_rate", "mean"))
        .reset_index()
        .sort_values("avg_er", ascending=False)
    )
    return [
        {col: (r[col].item() if hasattr(r[col], "item") else r[col]),
         "n": int(r["n"]), "avg_er": round(float(r["avg_er"]), 2)}
        for _, r in g.iterrows()
    ]


def niche_aggregates(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    d = df.copy()
    local = d["posted_at"].dt.tz_convert(_LOCAL_TZ)
    d["weekday"] = local.dt.weekday.map(lambda i: _WEEKDAYS[i] if pd.notna(i) else None)
    d["hour_bucket"] = pd.cut(
        local.dt.hour, bins=[-1, 6, 11, 14, 18, 21, 24],
        labels=["Nacht", "Vormittag", "Mittag", "Nachmittag", "Abend", "Spätabend"],
    )

    # Top-Hashtags der Nische nach Engagement (explodiert)
    rows = []
    for _, r in d.dropna(subset=["engagement_rate"]).iterrows():
        a = r.get("analysis")
        topics = a.get("topics") if isinstance(a, dict) else None
        for t in (topics or []):
            rows.append({"topic": t, "er": r["engagement_rate"]})
    topics_out = []
    if rows:
        td = pd.DataFrame(rows).groupby("topic").agg(
            n=("er", "size"), avg_er=("er", "mean")).reset_index()
        td = td[td["n"] >= 2].sort_values("avg_er", ascending=False)
        topics_out = [{"topic": r["topic"], "n": int(r["n"]), "avg_er": round(float(r["avg_er"]), 2)}
                      for _, r in td.head(12).iterrows()]

    return {
        "n_posts": int(len(d)),
        "n_accounts": int(d["account"].nunique()),
        "by_format": _er_by(d, "post_type"),
        "by_weekday": _er_by(d.dropna(subset=["weekday"]), "weekday"),
        "by_hour": _er_by(d.dropna(subset=["hour_bucket"]), "hour_bucket"),
        "top_topics": topics_out,
    }


NICHE_SYSTEM = """Du bist Senior-Stratege für Social-Media-Nischen. Du bekommst
aggregierte Performance-Daten EINER NISCHE (mehrere Accounts inkl. stärkerer
Wettbewerber) plus die besten Posts der Nische und die Muster des Ziel-Accounts.
Leite ab: wie in dieser Nische erfolgreich gepostet wird, und — als GAP-ANALYSE —
was genau der Ziel-Account davon übernehmen sollte. Begründe mit den Zahlen,
sei konkret, antworte auf Deutsch. Nutze IMMER das Tool save_niche_intel."""

NICHE_TOOL = {
    "name": "save_niche_intel",
    "description": "Nische-Intelligenz + Gap-Analyse für den Ziel-Account.",
    "input_schema": {
        "type": "object",
        "properties": {
            "niche_summary": {"type": "string", "description": "Wie die Nische tickt (2-4 Sätze)."},
            "winning_formats": {"type": "array", "items": {"type": "string"}, "description": "Formate, die in der Nische am besten performen."},
            "winning_hooks": {"type": "array", "items": {"type": "string"}, "description": "Hook-/Aufhänger-Muster der Top-Posts."},
            "best_timing": {"type": "string", "description": "Beste Tage/Zeiten laut Daten."},
            "topic_patterns": {"type": "array", "items": {"type": "string"}, "description": "Themen, die in der Nische ziehen."},
            "what_to_adapt": {"type": "array", "items": {"type": "string"}, "description": "GAP-ANALYSE: konkret, was der Ziel-Account übernehmen sollte (mit Bezug auf bessere Accounts)."},
            "opportunities": {"type": "array", "items": {"type": "string"}, "description": "Ungenutzte Chancen/Lücken in der Nische."},
        },
        "required": ["niche_summary", "winning_formats", "winning_hooks", "best_timing",
                     "topic_patterns", "what_to_adapt", "opportunities"],
    },
}


def build_niche_intel(username: str, platform: str | None = None) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    q = db.table("profiles").select("id").eq("username", username)
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    df = niche_dataframe(username, platform)
    if df.empty:
        raise RuntimeError("Keine Nische-Daten — erst Konkurrenten erfassen (bs-competitors).")
    agg = niche_aggregates(df)

    top = df.dropna(subset=["engagement_rate"]).sort_values("engagement_rate", ascending=False).head(15)
    top_posts = [
        {
            "account": r["account"], "is_own": bool(r["is_own"]),
            "post_type": r["post_type"], "er": round(float(r["engagement_rate"]), 2),
            "caption": (r["caption"] or "")[:160],
        }
        for _, r in top.iterrows()
    ]

    own = feature_aggregates(username)
    user = (
        f"ZIEL-ACCOUNT: @{username}\n\n"
        f"NISCHE-AGGREGATE (alle Accounts):\n```json\n{json.dumps(agg, ensure_ascii=False, indent=2)}\n```\n\n"
        f"TOP-POSTS DER NISCHE:\n```json\n{json.dumps(top_posts, ensure_ascii=False, indent=2)}\n```\n\n"
        f"MUSTER DES ZIEL-ACCOUNTS:\n```json\n{json.dumps({k: own.get(k) for k in ('by_format','by_weekday','by_content_format','top_topics')}, ensure_ascii=False, indent=2)}\n```"
    )
    intel = tool_call(NICHE_SYSTEM, user, NICHE_TOOL, max_tokens=4000)

    db.table("profile_insights").insert({
        "profile_id": prof[0]["id"],
        "kind": "niche",
        "payload": intel,
        "aggregates": agg,
        "model": get_settings().anthropic_model,
    }).execute()
    return {"intel": intel, "aggregates": agg, "n_accounts": agg.get("n_accounts")}


def latest_niche(username: str, platform: str | None = None) -> dict | None:
    db = get_client()
    q = db.table("profiles").select("id").eq("username", username.strip().lstrip("@"))
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        return None
    rows = (
        db.table("profile_insights").select("payload,aggregates,created_at")
        .eq("profile_id", prof[0]["id"]).eq("kind", "niche")
        .order("created_at", desc=True).limit(1).execute().data
    )
    return rows[0] if rows else None
