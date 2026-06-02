"""Headless-Smoke-Test der Multipage-Dashboard-Seiten via Streamlit AppTest.

Rendert jede Seite über ein Inline-Script (das das Seiten-Modul importiert und
render() aufruft) mit gesetztem Profil und meldet Exceptions. Testet beide Profile
(jonas = volle Daten, nasa = ohne Scores/Analysen), leere Filter und Post-Auswahl.
LLM-auslösende Buttons werden nicht geklickt.
"""

from __future__ import annotations

import sys

from streamlit.testing.v1 import AppTest

from blacksand.analytics import list_profiles

PAGE_NAMES = ["overview", "posts", "audience", "playbook", "forecast", "trends",
              "competitors", "niche", "transcripts"]

problems: list[str] = []


def _script(page: str, profile: dict) -> str:
    return (
        "import streamlit as st\n"
        f"st.session_state['profile'] = {profile!r}\n"
        f"from blacksand.dashboard.pages_ import {page} as _p\n"
        "_p.render()\n"
    )


def _run(page: str, profile: dict):
    return AppTest.from_string(_script(page, profile), default_timeout=90).run()


def _check(at, scenario: str):
    if at.exception:
        for e in at.exception:
            msg = getattr(e, "message", None) or getattr(e, "value", None) or str(e)
            problems.append(f"[{scenario}] {getattr(e, 'type', 'Exception')}: {msg}")
        print(f"  ✗ {scenario}: {len(at.exception)} Exception(s)")
    else:
        print(f"  ✓ {scenario}")


def main() -> None:
    profiles = list_profiles()
    print(f"Profile: {[p['username'] for p in profiles]}\n")

    for prof in profiles:
        u = prof["username"]
        print(f"--- @{u} ---")
        for page in PAGE_NAMES:
            _check(_run(page, prof), f"{u}: Seite '{page}'")

        # Posts: leere Filter
        at = _run("posts", prof)
        if at.multiselect:
            at.multiselect[0].set_value([]).run()
            _check(at, f"{u}: Posts leere Filter")

        # Posts: erste & letzte Post-Auswahl
        at = _run("posts", prof)
        post_sb = next((s for s in at.selectbox if s.label == "Post wählen"), None)
        if post_sb is not None and post_sb.options:
            for o in [post_sb.options[0], post_sb.options[-1]]:
                at2 = _run("posts", prof)
                sb = next(s for s in at2.selectbox if s.label == "Post wählen")
                sb.set_value(o).run()
                _check(at2, f"{u}: Post '{o[:28]}'")
        print()

    print("=" * 60)
    if problems:
        print(f"❌ {len(problems)} Problem(e):\n")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("✅ Keine Fehler auf allen Seiten/Pfaden.")


if __name__ == "__main__":
    main()
