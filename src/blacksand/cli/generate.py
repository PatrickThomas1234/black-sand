"""CLI: KI-Entwurfs-Generator.

Beispiel:
    uv run bs-generate jonas.greif44 "Erklär-Reel zu Reifenstrategie im Cup"
"""

from __future__ import annotations

import argparse

from ..generator import generate_concepts


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Entwurfs-Generator")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("brief", help="Thema/Ziel des Posts")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("-n", type=int, default=3, help="Anzahl Konzepte")
    args = parser.parse_args()

    concepts = generate_concepts(args.username, args.brief, n=args.n, platform=args.platform)
    print(f"\n=== {len(concepts)} POST-KONZEPTE @{args.username} ===\n")
    for i, c in enumerate(concepts, 1):
        pg = f" · P(gut)={c['prob_good']:.0%}" if "prob_good" in c else ""
        print(f"{i}. {c.get('title', '')}  [{c.get('format', '')}]{pg}")
        print(f"   Hook: {c.get('hook', '')}")
        print(f"   Caption: {c.get('caption', '')}")
        if c.get("hashtags"):
            print(f"   Hashtags: {' '.join('#' + h.lstrip('#') for h in c['hashtags'])}")
        print(f"   Zeit: {c.get('best_time', '—')}")
        print(f"   Warum: {c.get('rationale', '')}\n")


if __name__ == "__main__":
    main()
