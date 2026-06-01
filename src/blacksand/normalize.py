"""Normalisiert rohe Apify-Instagram-Items in unser DB-Schema.

Defensiv geschrieben: Apify-Felder variieren je nach Actor/Version, daher
überall .get() mit Fallbacks über bekannte Feldnamen-Varianten.
"""

from __future__ import annotations

from typing import Any

PLATFORM = "instagram"


def _first(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Gibt den ersten nicht-leeren Wert aus mehreren möglichen Keys zurück."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _post_type(item: dict[str, Any]) -> str:
    product = (item.get("productType") or "").lower()
    typ = (item.get("type") or "").lower()
    if product == "clips" or typ == "reel":
        return "reel"
    if typ == "sidecar":
        return "carousel"
    if typ == "video":
        return "video"
    if typ == "image":
        return "image"
    return "other"


def normalize_profile(item: dict[str, Any]) -> dict[str, Any]:
    """Mappt ein Apify 'details'-Item auf eine profiles-Row."""
    return {
        "platform": PLATFORM,
        "platform_user_id": _first(item, "id", "userId", "ownerId"),
        "username": _first(item, "username", "ownerUsername"),
        "full_name": _first(item, "fullName", "ownerFullName"),
        "biography": item.get("biography"),
        "follower_count": _first(item, "followersCount", "followers"),
        "following_count": _first(item, "followsCount", "followingCount"),
        "post_count": _first(item, "postsCount", "mediaCount"),
        "is_verified": _first(item, "verified", "isVerified"),
        "profile_pic_url": _first(item, "profilePicUrlHD", "profilePicUrl"),
        "external_url": _first(item, "externalUrl", "website"),
        "raw": item,
    }


def normalize_post(item: dict[str, Any], profile_id: str) -> dict[str, Any]:
    """Mappt ein Apify Post-Item auf eine posts-Row."""
    is_video = bool(
        item.get("videoUrl")
        or (item.get("type") or "").lower() == "video"
        or (item.get("productType") or "").lower() == "clips"
    )
    return {
        "profile_id": profile_id,
        "platform": PLATFORM,
        "platform_post_id": _first(item, "shortCode", "shortcode", "id", "code"),
        "url": _first(item, "url", "postUrl"),
        "post_type": _post_type(item),
        "caption": _first(item, "caption", "text"),
        "hashtags": item.get("hashtags") or [],
        "mentions": item.get("mentions") or [],
        "media_url": _first(item, "videoUrl", "displayUrl", "imageUrl"),
        "thumbnail_url": _first(item, "displayUrl", "thumbnailUrl"),
        "duration_seconds": _first(item, "videoDuration", "duration"),
        "is_video": is_video,
        "posted_at": _first(item, "timestamp", "takenAt", "takenAtTimestamp"),
        "raw": item,
    }


def extract_metrics(item: dict[str, Any]) -> dict[str, Any]:
    """Engagement-Metriken aus einem Post-Item (für metric_snapshots)."""
    return {
        "likes": _first(item, "likesCount", "likes"),
        "comments": _first(item, "commentsCount", "comments"),
        "views": _first(item, "videoViewCount", "viewCount", "views"),
        "plays": _first(item, "videoPlayCount", "playCount", "plays"),
        "shares": _first(item, "sharesCount", "shares"),
        "saves": _first(item, "savesCount", "saves"),
        "raw": {
            k: item.get(k)
            for k in (
                "likesCount",
                "commentsCount",
                "videoViewCount",
                "videoPlayCount",
            )
            if k in item
        },
    }
