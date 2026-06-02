"""CLI: Posts eines Profils mit Claude analysieren (Content-Insights).

Beispiel:
    uv run bs-analyze jonas.greif44 --limit 5
"""

from __future__ import annotations

import argparse

from ..analysis import analyze_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — LLM-Content-Analyse")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"], help="Plattform")
    parser.add_argument("--limit", type=int, default=None, help="Max. Anzahl Posts")
    parser.add_argument(
        "--redo", action="store_true", help="Auch bereits analysierte neu machen"
    )
    args = parser.parse_args()

    res = analyze_profile(args.username, limit=args.limit, redo=args.redo, platform=args.platform)
    print(f"\n✓ {res['analyzed']}/{res['attempted']} Posts analysiert.")


if __name__ == "__main__":
    main()
