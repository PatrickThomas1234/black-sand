"""Seite: Generator — KI erzeugt strategie-konforme Post-Konzepte."""

from __future__ import annotations

import streamlit as st

from blacksand.dashboard.shared import require_profile
from blacksand.generator import generate_concepts


def render() -> None:
    profile = require_profile()
    st.title("✍️ Entwurfs-Generator")
    st.caption("Erzeugt aus deinem Playbook + Nische-Intelligenz + aktuellen Trends "
               "konkrete Post-Konzepte — jedes mit datenbasierter P(guter Post).")

    with st.form("gen_form"):
        brief = st.text_area("Thema / Ziel", height=90,
                             placeholder="z.B. Erklär-Reel zur Reifenstrategie im Cup")
        n = st.slider("Anzahl Konzepte", 2, 5, 3)
        submitted = st.form_submit_button("✍️ Konzepte generieren", width="stretch")

    if not submitted:
        return
    if not brief.strip():
        st.warning("Bitte ein Thema eingeben.")
        return

    with st.spinner("Claude generiert Konzepte …"):
        concepts = generate_concepts(profile["username"], brief, n=n,
                                     platform=profile.get("platform"))
    if not concepts:
        st.info("Keine Konzepte erzeugt. Ggf. erst Playbook/Nische generieren.")
        return

    for i, c in enumerate(concepts, 1):
        pg = c.get("prob_good")
        badge = f" · 🎯 P(gut) {pg:.0%}" if pg is not None else ""
        with st.expander(f"{i}. {c.get('title', 'Konzept')} [{c.get('format', '')}]{badge}",
                         expanded=(i == 1)):
            st.markdown(f"**Hook:** {c.get('hook', '')}")
            st.markdown(f"**Caption:**\n\n{c.get('caption', '')}")
            if c.get("hashtags"):
                st.markdown("**Hashtags:** " + " ".join("#" + h.lstrip("#") for h in c["hashtags"]))
            st.markdown(f"**Beste Zeit:** {c.get('best_time', '—')}")
            st.markdown(f"**Warum:** {c.get('rationale', '')}")
