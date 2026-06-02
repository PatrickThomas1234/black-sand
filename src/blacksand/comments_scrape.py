"""TikTok-Kommentar-Ingestion (clockworks/tiktok-comments-scraper).

Der TikTok-Profil-Scraper liefert nur Kommentar-*Zahlen* — die Texte holen wir
separat über die Video-URLs und legen sie in `comments` ab (gleiche Tabelle wie
bei Instagram). Damit funktioniert die Publikums-/Sentiment-Analyse auch für TikTok.
"""

from __future__ import annotations

import re
from typing import Any

from . import apify
from .db import get_client
from .ingest import _coerce_timestamp

_VIDEO_ID = re.compile(r"/video/(\d+)")


def _video_id(url: str | None) -> str | None:
    if not url:
        return None
    m = _VIDEO_ID.search(url)
    return m.group(1) if m else None


def ingest_tiktok_comments(
    username: str, per_post: int = 50, max_posts: int | None = None
) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    prof = (
        db.table("profiles").select("id")
        .eq("username", username).eq("platform", "tiktok").execute().data
    )
    if not prof:
        raise RuntimeError(f"TikTok-Profil @{username} nicht in der DB.")

    posts = (
        db.table("posts").select("id,platform_post_id,url")
        .eq("profile_id", prof[0]["id"]).execute().data
    )
    id_by_video = {p["platform_post_id"]: p["id"] for p in posts}
    urls = [p["url"] for p in posts if p.get("url")]
    if max_posts:
        urls = urls[:max_posts]

    print(f"→ Scrape Kommentare für {len(urls)} TikTok-Videos …")
    items = apify.scrape_tiktok_comments(urls, per_post=per_post)
    print(f"  {len(items)} Kommentare erhalten.")

    rows, skipped = [], 0
    for c in items:
        vid = _video_id(c.get("submittedVideoUrl") or c.get("videoWebUrl"))
        post_id = id_by_video.get(vid)
        if not post_id or not (c.get("text") or "").strip():
            skipped += 1
            continue
        rows.append({
            "post_id": post_id,
            "platform_comment_id": str(c.get("cid") or c.get("id") or ""),
            "author": c.get("uniqueId"),
            "text": c.get("text"),
            "like_count": c.get("diggCount"),
            "posted_at": _coerce_timestamp(c.get("createTimeISO") or c.get("createTime")),
            "raw": c,
        })

    if rows:
        # in Batches upserten (Konflikt auf post_id+platform_comment_id)
        for i in range(0, len(rows), 500):
            db.table("comments").upsert(
                rows[i:i + 500], on_conflict="post_id,platform_comment_id"
            ).execute()

    print(f"  {len(rows)} Kommentare gespeichert ({skipped} übersprungen).")
    return {"profile": username, "comments": len(rows)}
