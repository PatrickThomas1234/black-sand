"""CLI: Publikums-/Kommentar-Analyse für ein Profil.

Beispiel:
    uv run bs-audience jonas.greif44
"""

from __future__ import annotations

import argparse

from ..audience import analyze_audience


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Publikums-Analyse")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"], help="Plattform")
    args = parser.parse_args()

    res = analyze_audience(args.username, platform=args.platform)
    a = res["audience"]
    print(f"\n=== PUBLIKUM @{args.username} ({res['n_comments']} Kommentare) ===\n")
    print(a["sentiment_overview"])
    print(f"Sentiment: 👍 {a['positive_pct']}% · ➖ {a['neutral_pct']}% · 👎 {a['negative_pct']}%\n")
    print("Top-Themen:", ", ".join(a.get("top_themes", [])))
    print("\nHäufige Fragen:")
    for q in a.get("frequent_questions", []):
        print(f"  ? {q}")
    print("\nLob:")
    for p in a.get("praise", []):
        print(f"  ✅ {p}")
    if a.get("criticism"):
        print("\nKritik:")
        for c in a["criticism"]:
            print(f"  🔻 {c}")
    print(f"\nPublikum: {a['audience_summary']}")
    print("\nFolgerungen für Content:")
    for ci in a.get("content_implications", []):
        print(f"  → {ci}")


if __name__ == "__main__":
    main()
