"""CLI: Konkurrenten relevanzbasiert finden & ingesten.

Beispiele:
    uv run bs-competitors jonas.greif44 --top 5
    uv run bs-competitors jonas.greif44 --discover-only
"""

from __future__ import annotations

import argparse

from ..competitors import build_competitors, discover_competitors


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Konkurrenz-Erkennung")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"])
    parser.add_argument("--top", type=int, default=5, help="Anzahl Konkurrenten")
    parser.add_argument("--shortlist", type=int, default=None,
                        help="Kandidaten-Pool zum Klassifizieren (Default: top×3, min 12)")
    parser.add_argument("--per-tag", type=int, default=30, help="Posts pro Hashtag")
    parser.add_argument("--max-posts", type=int, default=30, help="Posts pro Konkurrent beim Ingest")
    parser.add_argument("--discover-only", action="store_true", help="Nur finden, nicht ingesten")
    parser.add_argument("--hashtags", default=None,
                        help="Eigene Hashtags vorgeben (kommagetrennt), statt automatisch abzuleiten")
    args = parser.parse_args()
    shortlist = args.shortlist or max(args.top * 3, 12)
    tags = [h.strip().lstrip("#") for h in args.hashtags.split(",")] if args.hashtags else None

    if args.discover_only:
        d = discover_competitors(args.username, per_tag=args.per_tag, top_n=args.top,
                                 platform=args.platform, hashtags=tags)
        print(f"\nHashtags: {', '.join('#' + h for h in d['hashtags'])}\n")
        print(f"Top-{args.top} (von {len(d['ranked'])} Kandidaten):")
        for c in d["top"]:
            print(f"  @{c['username']} · {c['appearances']}x in {c['n_hashtags']} Hashtags "
                  f"· Engagement gesehen: {c['engagement_seen']:,}".replace(",", "."))
        return

    r = build_competitors(args.username, top_n=args.top, per_tag=args.per_tag,
                          max_posts=args.max_posts, shortlist=shortlist,
                          platform=args.platform, hashtags=tags)
    print(f"\n✓ Hashtags: {', '.join('#' + h for h in r['hashtags'])}")
    print("✓ Konkurrenten:")
    for c in r["competitors"]:
        tier = {"aspirational": "🔼 aspirational", "peer": "➖ peer", "smaller": "🔽 kleiner"}.get(c["tier"], c["tier"])
        print(f"   @{c['username']} · {c['account_type']} · {c['region']} · "
              f"{c['followers']} Follower · ER~{c['est_er']}% · {tier}")


if __name__ == "__main__":
    main()
