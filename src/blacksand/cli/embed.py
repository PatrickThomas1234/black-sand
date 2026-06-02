"""CLI: Post-Embeddings erzeugen/aktualisieren.

Beispiele:
    uv run bs-embed jonas.greif44
    uv run bs-embed --all
"""

from __future__ import annotations

import argparse

from ..embeddings import index_all, index_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Embeddings")
    parser.add_argument("username", nargs="?", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("--all", action="store_true", help="Alle Profile")
    parser.add_argument("--redo", action="store_true", help="Auch vorhandene neu berechnen")
    args = parser.parse_args()

    if args.all:
        res = index_all(redo=args.redo)
        print(f"\n✓ {sum(r.get('indexed', 0) for r in res)} Posts embedded ({len(res)} Profile).")
    elif args.username:
        r = index_profile(args.username, redo=args.redo, platform=args.platform)
        print(f"\n✓ {r['indexed']} Posts embedded für @{r['profile']}.")
    else:
        parser.error("Username angeben oder --all verwenden.")


if __name__ == "__main__":
    main()
