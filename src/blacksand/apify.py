"""Dünner Wrapper um den Apify Instagram-Scraper.

Wir machen zwei gezielte Actor-Runs pro Profil:
  1. resultsType="details" → Profil-Metadaten (Follower etc.)
  2. resultsType="posts"   → alle Posts bis `max_posts`

Das ist etwas teurer als ein kombinierter Run, dafür sind die Daten sauber
getrennt und zuverlässig (das 'details'-Item liefert Follower-Zahlen, die in
reinen Post-Items oft fehlen).
"""

from __future__ import annotations

from typing import Any

from apify_client import ApifyClient

from .config import get_settings


def _client() -> ApifyClient:
    s = get_settings()
    if not s.apify_token:
        raise RuntimeError(
            "APIFY_TOKEN fehlt in der .env. Token: "
            "https://console.apify.com/account/integrations"
        )
    return ApifyClient(s.apify_token)


def _run(actor: str, run_input: dict[str, Any]) -> list[dict[str, Any]]:
    client = _client()
    run = client.actor(actor).call(run_input=run_input)
    if run is None or not run.default_dataset_id:
        raise RuntimeError(f"Apify-Actor {actor} lieferte kein Dataset zurück.")
    return list(client.dataset(run.default_dataset_id).iterate_items())


def scrape_profile(username: str) -> dict[str, Any] | None:
    """Profil-Metadaten holen (Follower, Bio, …)."""
    s = get_settings()
    items = _run(
        s.apify_instagram_actor,
        {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "details",
            "resultsLimit": 1,
            "searchType": "user",
        },
    )
    return items[0] if items else None


def scrape_posts(username: str, max_posts: int = 200) -> list[dict[str, Any]]:
    """Bis zu `max_posts` Posts des Profils holen."""
    s = get_settings()
    return _run(
        s.apify_instagram_actor,
        {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "posts",
            "resultsLimit": max_posts,
            "searchType": "user",
            "addParentData": False,
        },
    )
