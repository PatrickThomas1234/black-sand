"""Engagement-Velocity — leichtgewichtiges Neu-Ziehen der Metriken.

Im Gegensatz zu `ingest` werden hier NUR die aktuellen Metriken gescrapt und als
neuer metric_snapshot abgelegt (keine Roh-Payloads, kein Post-Upsert). So entsteht
über wiederholte Läufe eine Zeitreihe pro Post — die Basis für das Velocity-Signal
(„wie schnell sammelt ein Post Likes/Views", v. a. in den ersten 24-48 h).

Ideal per Cron alle paar Stunden ausführen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import apify, normalize
from .db import get_client


def refresh_profile(username: str, max_posts: int = 200) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")

    prof = db.table("profiles").select("id").eq("username", username).execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB — erst `bs-ingest`.")
    profile_id = prof[0]["id"]

    # shortcode → post_id (nur bekannte Posts bekommen einen Snapshot)
    posts = (
        db.table("posts")
        .select("id,platform_post_id")
        .eq("profile_id", profile_id)
        .execute()
        .data
    )
    id_by_pid = {p["platform_post_id"]: p["id"] for p in posts}

    print(f"→ Refresh @{username}: scrape aktuelle Metriken …")
    items = apify.scrape_posts(username, max_posts=max_posts)
    now = datetime.now(timezone.utc).isoformat()

    snapshots, unknown = [], 0
    for it in items:
        pid = normalize._first(it, "shortCode", "shortcode", "id", "code")
        post_id = id_by_pid.get(pid)
        if not post_id:
            unknown += 1
            continue
        m = {k: v for k, v in normalize.extract_metrics(it).items() if v is not None}
        m["post_id"] = post_id
        m["captured_at"] = now
        snapshots.append(m)

    if snapshots:
        db.table("metric_snapshots").insert(snapshots).execute()
        db.table("posts").update({"last_scraped_at": now}).eq(
            "profile_id", profile_id
        ).in_("id", [s["post_id"] for s in snapshots]).execute()

    print(f"  {len(snapshots)} neue Snapshots ({unknown} neue/unbekannte Posts übersprungen).")
    return {"profile": username, "snapshots": len(snapshots), "new_posts_seen": unknown}


def refresh_all(max_posts: int = 200) -> list[dict[str, Any]]:
    db = get_client()
    profiles = db.table("profiles").select("username").execute().data
    results = []
    for p in profiles:
        try:
            results.append(refresh_profile(p["username"], max_posts=max_posts))
        except Exception as e:  # noqa: BLE001 — pro Profil tolerant
            print(f"  FEHLER @{p['username']}: {e}")
            results.append({"profile": p["username"], "error": str(e)})
    return results
