"""CLI: Velocity-Frühindikator für frische Posts.

Beispiel:
    uv run bs-early jonas.greif44 --days 14
"""

from __future__ import annotations

import argparse

from ..early import early_indicator

_ICON = {"viral": "🚀", "good": "✅", "avg": "➖", "below": "🔻", "flop": "❌"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Velocity-Frühindikator")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("--days", type=float, default=7.0, help="max. Alter in Tagen")
    args = parser.parse_args()

    rows = early_indicator(args.username, platform=args.platform, max_age_days=args.days)
    if not rows:
        print(f"Keine frischen Posts (≤ {args.days:.0f} Tage) für @{args.username}.")
        return
    print(f"\n=== Frühindikator @{args.username} ({len(rows)} frische Posts) ===\n")
    for r in rows:
        print(f"{_ICON.get(r['projected_rating'],'?')} Prognose {r['projected_rating']:6} "
              f"(z~{r['projected_z']:+.2f}, {r['confidence']}) · {r['age_h']:.0f}h alt "
              f"(~{r['matured_pct']}% ausgereift) · ER jetzt {r['current_er']} → proj. {r['projected_er']} "
              f"· {r['post_type']} · {r['shortcode']}")
        print(f"     {r['caption']!r}")


if __name__ == "__main__":
    main()
