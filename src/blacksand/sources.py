"""Plattform-Quellen-Abstraktion.

Jede Plattform liefert die gleichen Funktionen (scrape_profile/scrape_posts +
normalize_*), damit ingest/refresh plattform-agnostisch arbeiten. Neue Plattformen
(YouTube/LinkedIn) lassen sich so durch ein weiteres Source-Objekt ergänzen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import apify, normalize, normalize_tiktok


@dataclass(frozen=True)
class Source:
    platform: str
    raw_source: str                       # Label für raw_payloads.source
    scrape_profile: Callable[[str], dict | None]
    scrape_posts: Callable[..., list[dict]]
    normalize_profile: Callable[[dict], dict]
    normalize_post: Callable[[dict, str], dict]
    extract_metrics: Callable[[dict], dict]
    pid_keys: tuple[str, ...]             # Felder, aus denen die Post-ID gelesen wird


INSTAGRAM = Source(
    platform="instagram",
    raw_source="apify:instagram-scraper",
    scrape_profile=apify.scrape_profile,
    scrape_posts=apify.scrape_posts,
    normalize_profile=normalize.normalize_profile,
    normalize_post=normalize.normalize_post,
    extract_metrics=normalize.extract_metrics,
    pid_keys=("shortCode", "shortcode", "id", "code"),
)

TIKTOK = Source(
    platform="tiktok",
    raw_source="apify:tiktok-scraper",
    scrape_profile=apify.scrape_tiktok_profile,
    scrape_posts=apify.scrape_tiktok_posts,
    normalize_profile=normalize_tiktok.normalize_profile,
    normalize_post=normalize_tiktok.normalize_post,
    extract_metrics=normalize_tiktok.extract_metrics,
    pid_keys=("id", "videoId", "awemeId"),
)

_SOURCES = {s.platform: s for s in (INSTAGRAM, TIKTOK)}


def get_source(platform: str) -> Source:
    if platform not in _SOURCES:
        raise RuntimeError(
            f"Unbekannte Plattform '{platform}'. Verfügbar: {', '.join(_SOURCES)}"
        )
    return _SOURCES[platform]


def post_id_of(item: dict[str, Any], src: Source) -> str | None:
    return normalize._first(item, *src.pid_keys)
