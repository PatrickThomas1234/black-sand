"""Ingestion-Pipeline: Apify → normalisieren → Supabase.

Ablauf pro Profil:
  1. Profil + Posts von Apify scrapen
  2. Roh-Payloads in raw_payloads ablegen (Reproduzierbarkeit)
  3. profiles upserten → profile_id
  4. posts upserten
  5. metric_snapshots einfügen (eine Momentaufnahme pro Run = Zeitreihe)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import apify, normalize
from .db import get_client


def _coerce_timestamp(value: Any) -> str | None:
    """Wandelt Epoch-Sekunden/-Millis in ISO-8601, lässt ISO-Strings durch."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Heuristik: > 10^12 → Millisekunden
        seconds = value / 1000 if value > 1_000_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    return str(value)


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    """Entfernt None-Werte, damit DB-Defaults greifen."""
    return {k: v for k, v in row.items() if v is not None}


def ingest_profile(username: str, max_posts: int = 200) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")

    print(f"→ Scrape Profil @{username} …")
    profile_item = apify.scrape_profile(username)
    if not profile_item:
        raise RuntimeError(f"Kein Profil-Item für @{username} erhalten.")

    print(f"→ Scrape bis zu {max_posts} Posts …")
    post_items = apify.scrape_posts(username, max_posts=max_posts)
    print(f"  {len(post_items)} Posts erhalten.")

    # 2) Roh-Payloads sichern
    db.table("raw_payloads").insert(
        [
            {
                "source": "apify:instagram-scraper",
                "entity_type": "profile",
                "entity_ref": username,
                "payload": profile_item,
            },
            *[
                {
                    "source": "apify:instagram-scraper",
                    "entity_type": "post",
                    "entity_ref": normalize._first(p, "shortCode", "id"),
                    "payload": p,
                }
                for p in post_items
            ],
        ]
    ).execute()

    # 3) Profil upserten
    profile_row = _clean_row(normalize.normalize_profile(profile_item))
    profile_row["last_scraped_at"] = datetime.now(timezone.utc).isoformat()
    res = (
        db.table("profiles")
        .upsert(profile_row, on_conflict="platform,username")
        .execute()
    )
    profile_id = res.data[0]["id"]
    print(f"  Profil-ID: {profile_id}")

    # 4) Posts upserten
    post_rows: list[dict[str, Any]] = []
    for p in post_items:
        row = normalize.normalize_post(p, profile_id)
        if not row.get("platform_post_id"):
            continue
        row["posted_at"] = _coerce_timestamp(row.get("posted_at"))
        row["last_scraped_at"] = datetime.now(timezone.utc).isoformat()
        post_rows.append(_clean_row(row))

    if not post_rows:
        print("  Keine gültigen Posts zum Speichern.")
        return {"profile_id": profile_id, "posts": 0}

    res = (
        db.table("posts")
        .upsert(post_rows, on_conflict="platform,platform_post_id")
        .execute()
    )
    # shortcode → post_id
    id_by_pid = {r["platform_post_id"]: r["id"] for r in res.data}
    print(f"  {len(res.data)} Posts gespeichert.")

    # 5) Metric-Snapshots
    snapshots: list[dict[str, Any]] = []
    for p in post_items:
        pid = normalize._first(p, "shortCode", "shortcode", "id", "code")
        post_id = id_by_pid.get(pid)
        if not post_id:
            continue
        metrics = _clean_row(normalize.extract_metrics(p))
        metrics["post_id"] = post_id
        snapshots.append(metrics)

    if snapshots:
        db.table("metric_snapshots").insert(snapshots).execute()
        print(f"  {len(snapshots)} Metrik-Snapshots gespeichert.")

    return {"profile_id": profile_id, "posts": len(post_rows)}
