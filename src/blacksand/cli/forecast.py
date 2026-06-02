"""CLI: Performance-Prognose für einen Post-Entwurf.

Beispiel:
    uv run bs-forecast jonas.greif44 --type reel \\
        "Vergleichsvideo: Porsche GT3 Cup vs GT4 — was ist schneller?"
"""

from __future__ import annotations

import argparse

from ..forecast import forecast_post


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Post-Forecast")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"], help="Plattform")
    parser.add_argument("draft", help="Idee / Caption / Skript des geplanten Posts")
    parser.add_argument("--type", dest="post_type", default=None, help="Format, z.B. reel/carousel")
    args = parser.parse_args()

    f = forecast_post(args.username, args.draft, post_type=args.post_type, platform=args.platform)
    print(f"\n=== FORECAST @{args.username} ===\n")
    print(f"Prognose-Rating: {f['predicted_rating'].upper()}  "
          f"(ER ~{f['predicted_er_range']}, Konfidenz: {f['confidence']})\n")
    print(f"Begründung: {f['reasoning']}\n")
    print("Verbesserungen:")
    for i in f["improvements"]:
        print(f"  • {i}")
    print(f"\nOptimierter Hook: {f['optimized_hook']}")
    if f.get("optimized_caption"):
        print(f"\nOptimierte Caption:\n{f['optimized_caption']}")
    print(f"\nBester Zeitpunkt: {f['best_time']}")


if __name__ == "__main__":
    main()
