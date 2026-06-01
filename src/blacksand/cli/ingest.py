"""CLI: ein Instagram-Profil scrapen und in Supabase ablegen.

Beispiel:
    uv run bs-ingest natgeo --max-posts 100
"""

from __future__ import annotations

import argparse

from ..ingest import ingest_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Instagram-Ingestion")
    parser.add_argument("username", help="Instagram-Username (ohne @)")
    parser.add_argument(
        "--max-posts",
        type=int,
        default=200,
        help="Maximale Anzahl Posts (Default: 200)",
    )
    args = parser.parse_args()

    result = ingest_profile(args.username, max_posts=args.max_posts)
    print(f"\n✓ Fertig: {result['posts']} Posts für Profil {result['profile_id']}")


if __name__ == "__main__":
    main()
