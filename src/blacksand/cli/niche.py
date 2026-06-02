"""CLI: Nische-Intelligenz + Gap-Analyse (Account + Konkurrenten).

Beispiel:
    uv run bs-niche jonas.greif44
"""

from __future__ import annotations

import argparse

from ..niche_intel import build_niche_intel


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Nische-Intelligenz")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    args = parser.parse_args()

    res = build_niche_intel(args.username, platform=args.platform)
    intel = res["intel"]
    print(f"\n=== NISCHE-INTELLIGENZ @{args.username} ({res['n_accounts']} Accounts) ===\n")
    print(intel["niche_summary"], "\n")
    print("Gewinnende Formate:", ", ".join(intel.get("winning_formats", [])))
    print("Beste Zeit:", intel.get("best_timing"))
    print("\nGewinnende Hooks:")
    for h in intel.get("winning_hooks", []):
        print(f"  • {h}")
    print("\nThemen, die ziehen:", ", ".join(intel.get("topic_patterns", [])))
    print("\n→ DAS SOLLTEST DU ADAPTIEREN:")
    for w in intel.get("what_to_adapt", []):
        print(f"  ✦ {w}")
    print("\nUngenutzte Chancen:")
    for o in intel.get("opportunities", []):
        print(f"  ◇ {o}")


if __name__ == "__main__":
    main()
