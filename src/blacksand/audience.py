"""Build B — Publikums-/Kommentar-Analyse mit Claude.

Wertet alle gespeicherten Kommentare eines Kanals aus: Gesamtstimmung,
Sentiment-Verteilung, Top-Themen, häufige Fragen und Lob/Kritik. Das ist die
„Stimme des Publikums" — wertvoll, um Content an der Community auszurichten.

Hinweis: Aktuell liegen die per Apify mitgelieferten 'latestComments' vor (einige
pro Post). Für ALLE Kommentare bräuchte es einen dedizierten Kommentar-Scraper
pro Post (teurer) — später erweiterbar.
"""

from __future__ import annotations

from typing import Any

from .config import get_settings
from .db import get_client
from .llm import tool_call

SYSTEM = """Du bist ein Community-/Audience-Analyst für Social Media. Du bekommst
die Kommentare eines Instagram-Kanals (mit Post-Bezug). Analysiere die Stimme des
Publikums nüchtern und konkret: Gesamtstimmung, Sentiment-Verteilung, wiederkehrende
Themen, häufige Fragen und konkretes Lob bzw. Kritik. Leite ab, was das für die
Content-Strategie bedeutet. Antworte auf Deutsch. Nutze IMMER das Tool save_audience."""

TOOL = {
    "name": "save_audience",
    "description": "Speichert die Publikums-/Kommentar-Analyse eines Kanals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentiment_overview": {"type": "string", "description": "Gesamtstimmung in 1-2 Sätzen."},
            "positive_pct": {"type": "integer", "description": "Anteil positiver Kommentare (0-100)."},
            "neutral_pct": {"type": "integer", "description": "Anteil neutraler Kommentare (0-100)."},
            "negative_pct": {"type": "integer", "description": "Anteil negativer Kommentare (0-100)."},
            "top_themes": {"type": "array", "items": {"type": "string"}, "description": "Wiederkehrende Themen/Schlagworte."},
            "frequent_questions": {"type": "array", "items": {"type": "string"}, "description": "Häufig gestellte Fragen des Publikums."},
            "praise": {"type": "array", "items": {"type": "string"}, "description": "Wofür der Kanal konkret gelobt wird."},
            "criticism": {"type": "array", "items": {"type": "string"}, "description": "Kritik/Einwände (oder leer)."},
            "audience_summary": {"type": "string", "description": "Wer das Publikum ist und was es bewegt."},
            "content_implications": {"type": "array", "items": {"type": "string"}, "description": "Konkrete Folgerungen für den Content."},
        },
        "required": ["sentiment_overview", "positive_pct", "neutral_pct", "negative_pct",
                     "top_themes", "frequent_questions", "praise", "criticism",
                     "audience_summary", "content_implications"],
    },
}


def analyze_audience(username: str, platform: str | None = None) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    q = db.table("profiles").select("id").eq("username", username)
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")
    profile_id = prof[0]["id"]

    posts = (
        db.table("posts").select("id,platform_post_id,caption")
        .eq("profile_id", profile_id).execute().data
    )
    by_post = {p["id"]: p for p in posts}
    comments = (
        db.table("comments").select("post_id,author,text,like_count")
        .in_("post_id", list(by_post)).execute().data
    )
    if not comments:
        raise RuntimeError("Keine Kommentare gespeichert — erst `bs-backfill`.")

    lines = []
    for c in comments:
        if not (c.get("text") or "").strip():
            continue
        meta = by_post.get(c["post_id"], {})
        sc = meta.get("platform_post_id", "?")
        likes = c.get("like_count") or 0
        lines.append(f"[{sc}] {c.get('author') or '?'} (👍{likes}): {c['text'].strip()}")

    user = (
        f"KANAL: @{username}\n"
        f"{len(lines)} Kommentare:\n" + "\n".join(lines)
    )
    result = tool_call(SYSTEM, user, TOOL, max_tokens=3000)

    db.table("profile_insights").insert(
        {
            "profile_id": profile_id,
            "kind": "audience",
            "payload": result,
            "aggregates": {"n_comments": len(lines)},
            "model": get_settings().anthropic_model,
        }
    ).execute()
    return {"audience": result, "n_comments": len(lines)}


def latest_audience(username: str, platform: str | None = None) -> dict | None:
    db = get_client()
    q = db.table("profiles").select("id").eq("username", username.strip().lstrip("@"))
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        return None
    rows = (
        db.table("profile_insights")
        .select("payload,aggregates,model,created_at")
        .eq("profile_id", prof[0]["id"]).eq("kind", "audience")
        .order("created_at", desc=True).limit(1).execute().data
    )
    return rows[0] if rows else None
