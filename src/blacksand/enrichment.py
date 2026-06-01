"""Phase 2b — strukturiertes Backfill aus den gespeicherten Roh-Payloads.

Wir haben in raw_payloads bereits die kompletten Apify-Antworten. Hier extrahieren
wir die wertvollen Zusatzfelder in strukturierte Spalten/Tabellen — ohne erneut
zu scrapen. Das liefert Features fürs spätere Forecasting:
  * music            (Audio-Track: Original vs. Trending-Sound)
  * tagged_usernames (Kooperationen/Marken)
  * dimensions       (Format: Hoch-/Quer-/Quadrat)
  * audio_url
  * comments         (latestComments — Sentiment-/Themen-Signal)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .db import get_client
from .ingest import _coerce_timestamp


def _latest_raw_by_shortcode(db, refs: list[str]) -> dict[str, dict]:
    rows = (
        db.table("raw_payloads")
        .select("entity_ref,payload,fetched_at")
        .eq("entity_type", "post")
        .in_("entity_ref", refs)
        .order("fetched_at", desc=True)
        .execute()
        .data
    )
    out: dict[str, dict] = {}
    for r in rows:
        out.setdefault(r["entity_ref"], r["payload"])
    return out


def _tagged(payload: dict) -> list[str]:
    return [
        t.get("username")
        for t in (payload.get("taggedUsers") or [])
        if isinstance(t, dict) and t.get("username")
    ]


def _comments_rows(payload: dict, post_id: str) -> list[dict[str, Any]]:
    rows = []
    for i, c in enumerate(payload.get("latestComments") or []):
        if not isinstance(c, dict):
            continue
        cid = c.get("id") or f"{post_id}:{i}"
        rows.append(
            {
                "post_id": post_id,
                "platform_comment_id": str(cid),
                "author": c.get("ownerUsername") or c.get("owner", {}).get("username"),
                "text": c.get("text"),
                "like_count": c.get("likesCount"),
                "posted_at": _coerce_timestamp(c.get("timestamp")),
                "raw": c,
            }
        )
    return rows


def backfill_profile(username: str) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")

    prof = db.table("profiles").select("id").eq("username", username).execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    posts = (
        db.table("posts")
        .select("id,platform_post_id")
        .eq("profile_id", prof[0]["id"])
        .execute()
        .data
    )
    refs = [p["platform_post_id"] for p in posts]
    raw_by_ref = _latest_raw_by_shortcode(db, refs)

    updated, comments_total = 0, 0
    now = datetime.now(timezone.utc).isoformat()

    for p in posts:
        payload = raw_by_ref.get(p["platform_post_id"])
        if not payload:
            continue

        patch = {
            "music": payload.get("musicInfo"),
            "tagged_usernames": _tagged(payload),
            "audio_url": payload.get("audioUrl"),
            "last_scraped_at": now,
        }
        h, w = payload.get("dimensionsHeight"), payload.get("dimensionsWidth")
        if h and w:
            patch["dimensions"] = {"height": h, "width": w, "ratio": round(w / h, 3)}
        patch = {k: v for k, v in patch.items() if v not in (None, [], {})}

        db.table("posts").update(patch).eq("id", p["id"]).execute()
        updated += 1

        crows = _comments_rows(payload, p["id"])
        if crows:
            db.table("comments").upsert(
                crows, on_conflict="post_id,platform_comment_id"
            ).execute()
            comments_total += len(crows)

    return {"profile": username, "posts_updated": updated, "comments": comments_total}
