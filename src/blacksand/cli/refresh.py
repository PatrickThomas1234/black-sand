"""CLI: aktuelle Metriken neu ziehen (Velocity-Snapshots).

Beispiele:
    uv run bs-refresh jonas.greif44
    uv run bs-refresh --all
"""

from __future__ import annotations

import argparse

from ..refresh import refresh_all, refresh_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Metrik-Refresh (Velocity)")
    parser.add_argument("username", nargs="?", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("--all", action="store_true", help="Alle Profile refreshen")
    parser.add_argument("--max-posts", type=int, default=200)
    args = parser.parse_args()

    if args.all:
        res = refresh_all(max_posts=args.max_posts)
        total = sum(r.get("snapshots", 0) for r in res)
        print(f"\n✓ {len(res)} Profile, {total} neue Snapshots.")
    elif args.username:
        r = refresh_profile(args.username, max_posts=args.max_posts, platform=args.platform)
        print(f"\n✓ {r['snapshots']} neue Snapshots für @{r['profile']}.")
    else:
        parser.error("Bitte einen Username angeben oder --all verwenden.")


if __name__ == "__main__":
    main()
