"""CLI: Trend-Radar der Nische.

Beispiel:
    uv run bs-radar jonas.greif44 --days 45
"""

from __future__ import annotations

import argparse

from ..radar import niche_radar


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Trend-Radar")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("--days", type=int, default=45, help="jüngste Periode in Tagen")
    args = parser.parse_args()

    r = niche_radar(args.username, platform=args.platform, recent_days=args.days)
    if not r:
        print("Keine Nische-Daten — erst Konkurrenten erfassen (bs-competitors).")
        return
    print(f"\n=== TREND-RADAR @{args.username} (letzte {r['recent_days']} Tage, "
          f"{r['n_recent']} Posts) ===\n")
    print("🔥 Heiße Hashtags (Ø ER zuletzt · Trend):")
    for h in r["hot_hashtags"]:
        print(f"  {h['trend']} #{h['hashtag']:24} ER {h['recent_er']:5} (n={h['recent_n']})")
    print("\n🎬 Formate:")
    for f in r["hot_formats"]:
        print(f"  {f['trend']} {f['format']:10} ER {f['recent_er']} (n={f['recent_n']})")
    print("\n📈 Aufsteigende Accounts:")
    for a in r["surging_accounts"]:
        print(f"  @{a['account']:24} {a['change_pct']:+}% (ER {a['older_er']} → {a['recent_er']})")


if __name__ == "__main__":
    main()
