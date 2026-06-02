"""Seite: Publikum — Kommentar-Sentiment, Themen, Fragen + Kommentar-Browser."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.analytics import comments_df
from blacksand.audience import analyze_audience, latest_audience
from blacksand.dashboard.shared import require_profile


def render() -> None:
    profile = require_profile()
    st.title("💬 Publikum")
    st.caption("Was deine Community bewegt: Stimmung, Top-Themen, häufige Fragen sowie "
               "Lob & Kritik aus den Kommentaren.")

    cdf = comments_df(profile["username"], profile.get("platform"))
    aud = latest_audience(profile["username"], profile.get("platform"))

    c_l, c_r = st.columns([3, 1])
    c_l.caption(f"{len(cdf)} gespeicherte Kommentare.")
    with c_r:
        if st.button("🧠 Analyse (neu)", width="stretch", disabled=cdf.empty):
            with st.spinner("Claude analysiert die Kommentare …"):
                analyze_audience(profile["username"], profile.get("platform"))
            st.cache_data.clear()
            st.rerun()

    if cdf.empty:
        st.info("Keine Kommentare gespeichert. `uv run bs-backfill <user>` ausführen.")
        st.stop()

    if not aud:
        st.info("Noch keine Publikums-Analyse. Klicke auf **Analyse (neu)** "
                "(oder `uv run bs-audience <user>`).")
    else:
        a = aud["payload"]
        st.markdown(f"> {a.get('sentiment_overview', '')}")

        # Sentiment-Balken
        sent = pd.DataFrame({
            "Sentiment": ["positiv", "neutral", "negativ"],
            "Prozent": [a.get("positive_pct", 0), a.get("neutral_pct", 0), a.get("negative_pct", 0)],
        })
        st.altair_chart(
            alt.Chart(sent).mark_bar().encode(
                x=alt.X("Prozent:Q", title="%"),
                y=alt.Y("Sentiment:N", sort=["positiv", "neutral", "negativ"], title=None),
                color=alt.Color("Sentiment:N", scale=alt.Scale(
                    domain=["positiv", "neutral", "negativ"],
                    range=["#16a34a", "#a1a1aa", "#dc2626"]), legend=None),
            ).properties(height=140),
            width="stretch",
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Top-Themen**")
            for t in a.get("top_themes", []):
                st.markdown(f"- {t}")
            st.markdown("**❓ Häufige Fragen**")
            for q in a.get("frequent_questions", []):
                st.markdown(f"- {q}")
        with col2:
            st.markdown("**✅ Lob**")
            for p in a.get("praise", []):
                st.markdown(f"- {p}")
            if a.get("criticism"):
                st.markdown("**🔻 Kritik**")
                for c in a["criticism"]:
                    st.markdown(f"- {c}")

        st.info(f"**Publikum:** {a.get('audience_summary', '')}")
        st.markdown("**→ Folgerungen für Content**")
        for ci in a.get("content_implications", []):
            st.markdown(f"- {ci}")

    st.divider()
    st.markdown("**🔎 Kommentare durchsuchen**")
    q = st.text_input("Suche", placeholder="z.B. Frage, Lob, Wort …")
    view = cdf
    if q:
        view = cdf[cdf["text"].fillna("").str.contains(q, case=False)]
    st.dataframe(
        view[["like_count", "author", "text", "shortcode"]],
        width="stretch", hide_index=True,
        column_config={
            "like_count": st.column_config.NumberColumn("👍", width="small"),
            "author": st.column_config.TextColumn("Autor", width="small"),
            "text": st.column_config.TextColumn("Kommentar", width="large"),
        },
    )
