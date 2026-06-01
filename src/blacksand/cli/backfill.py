"""CLI: Zusatz-Metadaten aus den Roh-Payloads strukturieren (kein Re-Scrape).

Beispiel:
    uv run bs-backfill jonas.greif44
"""

from __future__ import annotations

import argparse

from ..enrichment import backfill_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Metadaten-Backfill")
    parser.add_argument("username", help="Instagram-Username (ohne @)")
    args = parser.parse_args()

    res = backfill_profile(args.username)
    print(
        f"✓ {res['posts_updated']} Posts aktualisiert, "
        f"{res['comments']} Kommentare gespeichert."
    )


if __name__ == "__main__":
    main()
