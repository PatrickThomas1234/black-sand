"""CLI: ein Profil scrapen und in Supabase ablegen.

Beispiele:
    uv run bs-ingest natgeo --max-posts 100
    uv run bs-ingest charlidamelio --platform tiktok --max-posts 100
"""

from __future__ import annotations

import argparse

from ..ingest import ingest_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Profil-Ingestion")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument(
        "--platform",
        default="instagram",
        choices=["instagram", "tiktok"],
        help="Plattform (Default: instagram)",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=200,
        help="Maximale Anzahl Posts (Default: 200)",
    )
    args = parser.parse_args()

    result = ingest_profile(args.username, max_posts=args.max_posts, platform=args.platform)
    print(f"\n✓ Fertig: {result['posts']} Posts für Profil {result['profile_id']}")


if __name__ == "__main__":
    main()
