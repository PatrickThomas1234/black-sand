"""CLI: Reel-Videos eines Profils transkribieren.

Beispiel:
    uv run bs-transcribe jonas.greif44 --limit 3
"""

from __future__ import annotations

import argparse

from ..transcription import transcribe_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Sand — Whisper-Transkription")
    parser.add_argument("username", help="Username (ohne @)")
    parser.add_argument("--platform", default="instagram", choices=["instagram", "tiktok"], help="Plattform")
    parser.add_argument("--limit", type=int, default=None, help="Max. Anzahl Videos")
    parser.add_argument(
        "--redo", action="store_true", help="Auch bereits transkribierte neu machen"
    )
    args = parser.parse_args()

    res = transcribe_profile(args.username, limit=args.limit, redo=args.redo, platform=args.platform)
    print(f"\n✓ {res['transcribed']}/{res['attempted']} Videos transkribiert.")


if __name__ == "__main__":
    main()
