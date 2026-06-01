"""CLI: datenbasiertes Content-Playbook für ein Profil erzeugen.

Beispiel:
    uv run bs-insights jonas.greif44
"""

from __future__ import annotations

import argparse

from ..insights import build_playbook


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Content-Playbook")
    parser.add_argument("username", help="Instagram-Username (ohne @)")
    args = parser.parse_args()

    res = build_playbook(args.username)
    pb = res["playbook"]
    print(f"\n=== PLAYBOOK @{args.username} ===\n")
    print(pb.get("summary", ""), "\n")
    print("STÄRKEN:")
    for s in pb.get("strengths", []):
        print(f"  ✅ {s}")
    print("\nSCHWÄCHEN:")
    for s in pb.get("weaknesses", []):
        print(f"  🔻 {s}")
    print("\nEMPFEHLUNGEN:")
    for r in pb.get("recommendations", []):
        print(f"  • [{r.get('area')}] {r.get('advice')}\n      ↳ {r.get('evidence')}")
    print("\nNÄCHSTE POST-IDEEN:")
    for i in pb.get("content_ideas", []):
        print(f"  💡 {i.get('title', '')}")
        if i.get("hook"):
            print(f"      Hook: {i['hook']}")
        if i.get("rationale"):
            print(f"      Warum: {i['rationale']}")
    bp = pb.get("best_pattern", {})
    print(f"\nOPTIMALES REZEPT: {bp.get('format')} · {bp.get('weekday')} {bp.get('time')} · "
          f"{bp.get('caption_style')} · {bp.get('audio')}")


if __name__ == "__main__":
    main()
