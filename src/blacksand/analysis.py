"""Phase 2c — LLM-Content-Analyse mit Claude.

Pro Post bündeln wir alles, was wir haben (Caption, Transkript, Post-Typ,
Performance-Score, Musik, Tags) und lassen Claude strukturiert extrahieren:
Hook, Format, Themen, Struktur, Tonalität, CTA — plus eine Hypothese, *warum*
der Post so performt hat. Genau diese Features sind später die Basis fürs
Forecasting ("so musst du posten").

Strukturierte Ausgabe via Tool-Use (erzwungen), System-Prompt wird gecacht.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .config import get_settings
from .db import get_client

SYSTEM = """Du bist ein erfahrener Social-Media-Analyst für Instagram-Content.
Du bekommst einen einzelnen Post (Caption, ggf. Transkript des Videos, Post-Typ,
Performance-Kennzahlen relativ zum Kanal und Metadaten). Analysiere ihn nüchtern
und konkret auf Deutsch. Vermeide Floskeln; sei spezifisch und datennah.
Nutze IMMER das Tool save_analysis, um deine Analyse zurückzugeben."""

TOOL = {
    "name": "save_analysis",
    "description": "Speichert die strukturierte Content-Analyse eines Posts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "hook": {
                "type": "string",
                "description": "Der Aufhänger der ersten Sekunden/Zeile — wörtlich oder zusammengefasst.",
            },
            "content_format": {
                "type": "string",
                "description": "Format, z.B. Vergleichsvideo, Tutorial, Vlog, Talking-Head, Behind-the-Scenes, Ankündigung, Story-Carousel.",
            },
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-6 zentrale Themen/Schlagworte.",
            },
            "structure": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Der Aufbau in Schritten (Hook → ... → CTA).",
            },
            "tone": {"type": "string", "description": "Tonalität, z.B. informativ, emotional, humorvoll, werblich."},
            "cta": {"type": "string", "description": "Call-to-Action, falls vorhanden (sonst 'keiner')."},
            "summary": {"type": "string", "description": "1-2 Sätze, worum es geht."},
            "performance_drivers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Hypothesen, WARUM dieser Post (gemessen am Rating) so performt hat — content-seitig begründet.",
            },
        },
        "required": ["hook", "content_format", "topics", "structure", "tone", "cta", "summary", "performance_drivers"],
    },
}


@lru_cache
def _client():
    from anthropic import Anthropic

    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY fehlt in der .env — für die LLM-Analyse benötigt."
        )
    return Anthropic(api_key=s.anthropic_api_key)


def _build_user_content(post: dict[str, Any]) -> str:
    parts = [
        f"POST-TYP: {post.get('post_type')}",
        f"PERFORMANCE: Rating={post.get('rating')} | "
        f"Engagement-Rate={post.get('engagement_rate')}% | z-Score={post.get('zscore')} "
        f"(relativ zur Kanal-Baseline)",
        f"KENNZAHLEN: 👍{post.get('likes')} 💬{post.get('comments')} 👁{post.get('views')}",
    ]
    if post.get("music"):
        m = post["music"]
        orig = m.get("uses_original_audio")
        parts.append(
            f"AUDIO: {'Original-Audio' if orig else 'fremder/Trending-Sound'} "
            f"— {m.get('song_name')} / {m.get('artist_name')}"
        )
    if post.get("tagged_usernames"):
        parts.append(f"MARKIERTE ACCOUNTS: {', '.join(post['tagged_usernames'])}")
    parts.append(f"\nCAPTION:\n{post.get('caption') or '(keine)'}")
    if post.get("transcript"):
        parts.append(f"\nTRANSKRIPT:\n{post['transcript']}")
    return "\n".join(parts)


def analyze_one(post: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    resp = _client().messages.create(
        model=s.anthropic_model,
        max_tokens=1500,
        system=[
            {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}
        ],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "save_analysis"},
        messages=[{"role": "user", "content": _build_user_content(post)}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Kein tool_use im Claude-Response.")


def _gather_posts(db, profile_id: str) -> list[dict[str, Any]]:
    """Posts + jüngstes Transkript + jüngster Score zusammenführen."""
    posts = (
        db.table("posts")
        .select("id,platform_post_id,post_type,caption,music,tagged_usernames")
        .eq("profile_id", profile_id)
        .execute()
        .data
    )
    ids = [p["id"] for p in posts]

    tr = db.table("transcripts").select("post_id,text").in_("post_id", ids).execute().data
    tr_by = {t["post_id"]: t["text"] for t in tr}

    sc = (
        db.table("performance_scores")
        .select("post_id,engagement_rate,baseline_zscore,rating,computed_at")
        .in_("post_id", ids)
        .order("computed_at", desc=True)
        .execute()
        .data
    )
    sc_by: dict[str, dict] = {}
    for r in sc:
        sc_by.setdefault(r["post_id"], r)

    ms = db.table("metric_snapshots").select("post_id,likes,comments,views,captured_at").in_("post_id", ids).order("captured_at", desc=True).execute().data
    m_by: dict[str, dict] = {}
    for r in ms:
        m_by.setdefault(r["post_id"], r)

    for p in posts:
        p["transcript"] = tr_by.get(p["id"])
        s = sc_by.get(p["id"], {})
        p["rating"] = s.get("rating")
        p["engagement_rate"] = s.get("engagement_rate")
        p["zscore"] = s.get("baseline_zscore")
        m = m_by.get(p["id"], {})
        p["likes"], p["comments"], p["views"] = m.get("likes"), m.get("comments"), m.get("views")
    return posts


def analyze_profile(
    username: str, limit: int | None = None, redo: bool = False, platform: str | None = None
) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    q = db.table("profiles").select("id").eq("username", username)
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    posts = _gather_posts(db, prof[0]["id"])

    if not redo:
        done = {a["post_id"] for a in db.table("content_analysis").select("post_id").execute().data}
        posts = [p for p in posts if p["id"] not in done]
    if limit:
        posts = posts[:limit]

    print(f"→ {len(posts)} Post(s) zu analysieren (Modell: {get_settings().anthropic_model}).")
    ok = 0
    for i, p in enumerate(posts, 1):
        try:
            analysis = analyze_one(p)
            row = {
                "post_id": p["id"],
                "model": get_settings().anthropic_model,
                "hook": analysis.get("hook"),
                "topics": analysis.get("topics"),
                "structure": analysis.get("structure"),
                "tone": analysis.get("tone"),
                "cta": analysis.get("cta"),
                "summary": analysis.get("summary"),
                "analysis": analysis,
            }
            db.table("content_analysis").upsert(row, on_conflict="post_id").execute()
            ok += 1
            print(f"  [{i}/{len(posts)}] {p['platform_post_id']} [{p.get('rating')}]: {analysis.get('content_format')}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{len(posts)}] {p['platform_post_id']}: FEHLER {e}")

    return {"profile": username, "analyzed": ok, "attempted": len(posts)}
