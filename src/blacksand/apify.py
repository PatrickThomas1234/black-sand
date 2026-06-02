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


def scrape_hashtag(tag: str, limit: int = 30) -> list[dict[str, Any]]:
    """Aktuelle Top-Posts zu einem Hashtag (für Konkurrenz-Discovery)."""
    s = get_settings()
    tag = tag.lstrip("#")
    return _run(
        s.apify_instagram_actor,
        {
            "directUrls": [f"https://www.instagram.com/explore/tags/{tag}/"],
            "resultsType": "posts",
            "resultsLimit": limit,
            "searchType": "hashtag",
        },
    )


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


# --- TikTok (clockworks/tiktok-scraper) ----------------------------------
# Der Actor liefert pro Video ein Item; die Profil-Metadaten stecken in
# item["authorMeta"]. Ein Run reicht für Profil + Posts.

def scrape_tiktok_posts(username: str, max_posts: int = 100) -> list[dict[str, Any]]:
    s = get_settings()
    return _run(
        s.apify_tiktok_actor,
        {
            "profiles": [username.lstrip("@")],
            "resultsPerPage": max_posts,
            # Videos + Cover laden → mediaUrls/Thumbnails verfügbar für Vision & Whisper
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": True,
            "shouldDownloadSubtitles": False,
            "shouldDownloadSlideshowImages": False,
        },
    )


def scrape_tiktok_profile(username: str) -> dict[str, Any] | None:
    """Profil-Metadaten = authorMeta des ersten Video-Items."""
    items = scrape_tiktok_posts(username, max_posts=1)
    if not items:
        return None
    author = items[0].get("authorMeta")
    return author if isinstance(author, dict) and author else items[0]


def scrape_tiktok_comments(post_urls: list[str], per_post: int = 50) -> list[dict[str, Any]]:
    """Kommentare zu TikTok-Videos (clockworks/tiktok-comments-scraper)."""
    if not post_urls:
        return []
    s = get_settings()
    return _run(
        s.apify_tiktok_comments_actor,
        {
            "postURLs": post_urls,
            "commentsPerPost": per_post,
            "maxRepliesPerComment": 0,
        },
    )


def scrape_tiktok_hashtag(tag: str, limit: int = 50) -> list[dict[str, Any]]:
    """Aktuelle Videos zu einem TikTok-Hashtag (für Konkurrenz-Discovery).

    Items enthalten authorMeta (Follower/Bio) → Ranking ohne Extra-Scrape möglich.
    """
    s = get_settings()
    return _run(
        s.apify_tiktok_hashtag_actor,
        {"hashtags": [tag.lstrip("#")], "resultsPerPage": limit},
    )
