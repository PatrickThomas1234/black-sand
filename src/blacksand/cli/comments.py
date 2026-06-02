"""CLI: Kommentare ziehen.

Instagram: kommen über `bs-backfill` (latestComments).
TikTok:    eigener Kommentar-Scraper über die Video-URLs.

Beispiel:
    uv run bs-comments jonas.greif44 --platform tiktok --per-post 50
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Kommentar-Ingestion")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="tiktok", choices=["instagram", "tiktok"])
    parser.add_argument("--per-post", type=int, default=50, help="Kommentare pro Post")
    parser.add_argument("--max-posts", type=int, default=None)
    args = parser.parse_args()

    if args.platform == "tiktok":
        from ..comments_scrape import ingest_tiktok_comments
        res = ingest_tiktok_comments(args.username, per_post=args.per_post, max_posts=args.max_posts)
        print(f"\n✓ {res['comments']} TikTok-Kommentare für @{res['profile']}.")
    else:
        from ..enrichment import backfill_profile
        res = backfill_profile(args.username)
        print(f"\n✓ {res['comments']} Kommentare (Instagram-Backfill) für @{res['profile']}.")


if __name__ == "__main__":
    main()
