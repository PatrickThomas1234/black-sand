"""Normalisiert rohe TikTok-Items (clockworks/tiktok-scraper) in unser Schema.

Defensiv geschrieben — Feldnamen variieren je Actor-Version.
"""

from __future__ import annotations

from typing import Any

from .normalize import _first  # gemeinsamer Helfer

PLATFORM = "tiktok"


def normalize_profile(item: dict[str, Any]) -> dict[str, Any]:
    """`item` ist authorMeta (oder ein Video-Item mit authorMeta)."""
    a = item.get("authorMeta") if isinstance(item.get("authorMeta"), dict) else item
    return {
        "platform": PLATFORM,
        "platform_user_id": _first(a, "id", "userId", "secUid"),
        "username": _first(a, "name", "uniqueId", "nickName"),
        "full_name": _first(a, "nickName", "nickname"),
        "biography": _first(a, "signature", "bio"),
        "follower_count": _first(a, "fans", "followerCount", "followers"),
        "following_count": _first(a, "following", "followingCount"),
        "post_count": _first(a, "video", "videoCount", "videos"),
        "is_verified": _first(a, "verified", "isVerified"),
        "profile_pic_url": _first(a, "avatar", "avatarLarger", "avatarMedium"),
        "external_url": _first(a, "bioLink", "website"),
        "raw": a,
    }


def _hashtags(item: dict[str, Any]) -> list[str]:
    out = []
    for h in item.get("hashtags") or []:
        if isinstance(h, dict) and h.get("name"):
            out.append(h["name"])
        elif isinstance(h, str):
            out.append(h.lstrip("#"))
    return out


def normalize_post(item: dict[str, Any], profile_id: str) -> dict[str, Any]:
    vmeta = item.get("videoMeta") or {}
    media = (
        _first(item, "videoUrl", "downloadAddr", "playAddr")
        or (item.get("mediaUrls") or [None])[0]
    )
    return {
        "profile_id": profile_id,
        "platform": PLATFORM,
        "platform_post_id": _first(item, "id", "videoId", "awemeId"),
        "url": _first(item, "webVideoUrl", "url"),
        "post_type": "video",
        "caption": _first(item, "text", "desc", "caption"),
        "hashtags": _hashtags(item),
        "mentions": item.get("mentions") or [],
        "media_url": media,
        "thumbnail_url": _first(vmeta, "coverUrl", "originCover") or item.get("covers"),
        "duration_seconds": _first(vmeta, "duration") or _first(item, "videoDuration"),
        "is_video": True,
        "posted_at": _first(item, "createTimeISO", "createTime", "createTimestamp"),
        "raw": item,
    }


def extract_metrics(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "likes": _first(item, "diggCount", "likesCount", "likes"),
        "comments": _first(item, "commentCount", "commentsCount", "comments"),
        "views": _first(item, "playCount", "viewCount", "views"),
        "plays": _first(item, "playCount", "plays"),
        "shares": _first(item, "shareCount", "shares"),
        "saves": _first(item, "collectCount", "saveCount", "saves"),
        "raw": {
            k: item.get(k)
            for k in ("diggCount", "commentCount", "playCount", "shareCount", "collectCount")
            if k in item
        },
    }
