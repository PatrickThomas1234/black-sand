"""CLI: Performance-Scores für ein bereits ingestetes Profil berechnen.

Beispiel:
    uv run bs-score jonas.greif44
"""

from __future__ import annotations

import argparse

from ..scoring import score_profile

_ICON = {"viral": "🚀", "good": "✅", "avg": "➖", "below": "🔻", "flop": "❌"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Performance-Scoring")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"], help="Plattform")
    args = parser.parse_args()

    result = score_profile(args.username, platform=args.platform)
    rows = result.get("rows", [])
    if not rows:
        print(f"Keine Posts für @{result['profile']} gefunden.")
        return

    rows.sort(key=lambda r: r["algo_zscore"], reverse=True)
    print(f"\n=== Performance @{result['profile']} ({result['scored']} Posts) ===\n")
    print(f"{'':2} {'rating':6} {'algoZ':>6} {'engZ':>6} {'ER%':>6} {'reach%':>7} {'typ':8}  caption")
    for r in rows:
        vr = f"{r['view_rate']:7.0f}" if r.get("view_rate") is not None else f"{'—':>7}"
        print(
            f"{_ICON.get(r['rating'],'?'):2} {r['rating']:6} "
            f"{r['algo_zscore']:6.2f} {r['baseline_zscore']:6.2f} "
            f"{r['engagement_rate']:6.2f} {vr} {r['_post_type']:8}  {r['_caption']!r}"
        )


if __name__ == "__main__":
    main()
