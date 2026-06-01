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
    parser.add_argument("username", help="Instagram-Username (ohne @)")
    args = parser.parse_args()

    result = score_profile(args.username)
    rows = result.get("rows", [])
    if not rows:
        print(f"Keine Posts für @{result['profile']} gefunden.")
        return

    rows.sort(key=lambda r: r["baseline_zscore"], reverse=True)
    print(f"\n=== Performance @{result['profile']} ({result['scored']} Posts) ===\n")
    print(f"{'':2} {'rating':6} {'z':>6} {'ER%':>6} {'typ':8} {'scope':8}  caption")
    for r in rows:
        d = r["details"]
        print(
            f"{_ICON.get(r['rating'],'?'):2} {r['rating']:6} "
            f"{r['baseline_zscore']:6.2f} {r['engagement_rate']:6.2f} "
            f"{r['_post_type']:8} {d['baseline_scope']:8}  {r['_caption']!r}"
        )


if __name__ == "__main__":
    main()
