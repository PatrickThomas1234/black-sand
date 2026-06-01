"""Seite: Playbook — LLM-Synthese + Aggregat-Charts."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.dashboard.shared import require_profile
from blacksand.insights import build_playbook, latest_playbook


def render() -> None:
    profile = require_profile()
    st.title("🎯 Content-Playbook")

    pb = latest_playbook(profile["username"])
    c_l, c_r = st.columns([3, 1])
    with c_r:
        if st.button("🧠 Playbook generieren", width="stretch"):
            with st.spinner("Claude analysiert die Muster …"):
                build_playbook(profile["username"])
            st.cache_data.clear()
            st.rerun()

    if not pb:
        st.info("Noch kein Playbook. Klicke auf **Playbook generieren** "
                "(oder `uv run bs-insights <user>`).")
        st.stop()

    p = pb["payload"]
    agg = pb["aggregates"] or {}
    st.caption(f"Modell: {pb.get('model')} · erstellt: {str(pb.get('created_at', ''))[:16]}")
    st.markdown(f"> {p.get('summary', '')}")

    cs, cw = st.columns(2)
    with cs:
        st.markdown("**✅ Stärken**")
        for s in p.get("strengths", []):
            st.markdown(f"- {s}")
    with cw:
        st.markdown("**🔻 Schwächen**")
        for s in p.get("weaknesses", []):
            st.markdown(f"- {s}")

    st.markdown("**📋 Empfehlungen**")
    for r in p.get("recommendations", []):
        st.markdown(f"- **[{r.get('area', '')}]** {r.get('advice', '')}  \n  _↳ {r.get('evidence', '')}_")

    st.markdown("**💡 Nächste Post-Ideen**")
    for idea in p.get("content_ideas", []):
        if idea.get("hook") or idea.get("rationale"):
            with st.expander(f"{idea.get('title', 'Idee')} ({idea.get('format', '')})"):
                if idea.get("hook"):
                    st.markdown(f"**Hook:** {idea['hook']}")
                if idea.get("rationale"):
                    st.markdown(f"**Warum:** {idea['rationale']}")
        else:
            st.markdown(f"- {idea.get('title', '')}")

    bp = p.get("best_pattern", {})
    st.success(
        f"**Optimales Rezept:** {bp.get('format', '—')} · {bp.get('weekday', '—')} "
        f"{bp.get('time', '')} · {bp.get('caption_style', '')} · {bp.get('audio', '')}"
    )

    st.divider()
    st.markdown("**📊 Muster (Ø z-Score je Gruppe)**")

    def _chart(key: str, dim: str, title: str):
        rows = agg.get(key, [])
        if not rows:
            return
        adf = pd.DataFrame(rows)
        st.altair_chart(
            alt.Chart(adf).mark_bar().encode(
                x=alt.X(f"{dim}:N", sort="-y", title=title),
                y=alt.Y("avg_z:Q", title="Ø z-Score"),
                color=alt.condition(alt.datum.avg_z > 0, alt.value("#16a34a"), alt.value("#dc2626")),
                tooltip=[dim, "n", "avg_z", "avg_er"],
            ).properties(height=220),
            width="stretch",
        )

    g1, g2 = st.columns(2)
    with g1:
        _chart("by_weekday", "weekday", "Wochentag")
        _chart("by_caption_length", "caption_len_bucket", "Caption-Länge")
    with g2:
        _chart("by_hour_bucket", "hour_bucket", "Tageszeit")
        _chart("by_content_format", "format_llm", "Format (KI)")
