"""CLI: Content-Kalender / Posting-Plan.

Beispiel:
    uv run bs-calendar jonas.greif44 --weeks 2
"""

from __future__ import annotations

import argparse

from ..planner import build_calendar


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Content-Kalender")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("--weeks", type=int, default=2)
    args = parser.parse_args()

    plan = build_calendar(args.username, weeks=args.weeks, platform=args.platform)
    print(f"\n=== CONTENT-KALENDER @{args.username} ({len(plan)} Posts) ===\n")
    for p in plan:
        print(f"📅 {p.get('slot', '')}  [{p.get('format', '')}]")
        print(f"   Thema: {p.get('topic', '')}")
        print(f"   Hook: {p.get('hook', '')}")
        if p.get("rationale"):
            print(f"   Warum: {p['rationale']}")
        print()


if __name__ == "__main__":
    main()
