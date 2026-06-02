"""Seite: Nische — wie die Nische erfolgreich postet + Gap-Analyse."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.dashboard.shared import require_profile
from blacksand.niche_intel import build_niche_intel, latest_niche, niche_usernames


def render() -> None:
    profile = require_profile()
    me = profile["username"]
    plat = profile.get("platform")
    st.title("🌍 Nische-Intelligenz")
    st.caption("Wie deine Nische erfolgreich postet — plus Gap-Analyse: was genau DU "
               "davon adaptieren solltest.")

    _, comp = niche_usernames(me, plat)
    n = latest_niche(me, plat)

    c_l, c_r = st.columns([3, 1])
    c_l.caption(f"Basis: dein Account + {len(comp)} Konkurrenten.")
    with c_r:
        if st.button("🧠 Nische analysieren", width="stretch", disabled=not comp):
            with st.spinner("Claude wertet die Nische aus …"):
                build_niche_intel(me, plat)
            st.cache_data.clear()
            st.rerun()

    if not comp:
        st.info("Noch keine Konkurrenten erfasst. Erst `uv run bs-competitors " + me + "` ausführen.")
        st.stop()
    if not n:
        st.info("Noch keine Nische-Analyse. Klicke auf **Nische analysieren** "
                f"(oder `uv run bs-niche {me}`).")
        st.stop()

    p = n["payload"]
    agg = n["aggregates"] or {}
    st.markdown(f"> {p.get('niche_summary', '')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🏆 Gewinnende Formate**")
        for f in p.get("winning_formats", []):
            st.markdown(f"- {f}")
        st.markdown(f"**⏰ Beste Zeit:** {p.get('best_timing', '')}")
        st.markdown("**🧲 Gewinnende Hooks**")
        for h in p.get("winning_hooks", []):
            st.markdown(f"- {h}")
    with col2:
        st.markdown("**🔖 Themen, die ziehen**")
        for t in p.get("topic_patterns", []):
            st.markdown(f"- {t}")
        st.markdown("**🧭 Ungenutzte Chancen**")
        for o in p.get("opportunities", []):
            st.markdown(f"- {o}")

    st.divider()
    st.markdown("### ✦ Das solltest **du** adaptieren (Gap-Analyse)")
    for w in p.get("what_to_adapt", []):
        st.success(w)

    st.divider()
    st.markdown("**📊 Engagement-Rate in der Nische**")
    g1, g2 = st.columns(2)

    def _chart(rows, dim, title, container):
        if not rows:
            return
        adf = pd.DataFrame(rows)
        container.altair_chart(
            alt.Chart(adf).mark_bar().encode(
                x=alt.X(f"{dim}:N", sort="-y", title=title),
                y=alt.Y("avg_er:Q", title="Ø ER %"),
                tooltip=[dim, "n", "avg_er"],
            ).properties(height=240),
            width="stretch",
        )

    _chart(agg.get("by_format"), "post_type", "Format", g1)
    _chart(agg.get("by_weekday"), "weekday", "Wochentag", g2)
