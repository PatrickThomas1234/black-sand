"""Seite: Content-Kalender — KI-Posting-Plan."""

from __future__ import annotations

import streamlit as st

from blacksand.dashboard.shared import require_profile
from blacksand.planner import build_calendar


def render() -> None:
    profile = require_profile()
    st.title("🗓️ Content-Kalender")
    st.caption("Ein Posting-Plan, der beste Zeiten + erfolgreiche Formate/Themen + "
               "aktuelle Trends kombiniert. Aus Erkenntnissen wird ein Fahrplan.")

    c1, c2, c3 = st.columns([1, 1, 2])
    weeks = c1.number_input("Wochen", 1, 6, 2)
    if not c2.button("🗓️ Plan erstellen", width="stretch"):
        st.stop()

    with st.spinner("Claude plant …"):
        plan = build_calendar(profile["username"], weeks=int(weeks),
                              platform=profile.get("platform"))
    if not plan:
        st.info("Kein Plan erzeugt. Ggf. erst Playbook/Nische generieren.")
        return

    for p in plan:
        with st.container(border=True):
            st.markdown(f"**📅 {p.get('slot', '')}**  ·  _{p.get('format', '')}_")
            st.markdown(f"**Thema:** {p.get('topic', '')}")
            st.markdown(f"**Hook:** {p.get('hook', '')}")
            if p.get("rationale"):
                st.caption(p["rationale"])
