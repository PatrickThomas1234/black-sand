"""Seite: Forecast — Performance-Prognose für einen Post-Entwurf."""

from __future__ import annotations

import streamlit as st

from blacksand.dashboard.shared import require_profile
from blacksand.forecast import forecast_post

_RATING_HELP = "Erwartetes Rating relativ zur Kanal-Baseline (flop … viral)."


def render() -> None:
    profile = require_profile()
    st.title("🔮 Post-Forecast")
    st.caption("Prüfe einen Entwurf, bevor du postest — Prognose + Verbesserungen "
               "auf Basis der gelernten Kanal-Muster.")

    with st.form("forecast_form"):
        draft = st.text_area("Idee / Caption / Skript des geplanten Posts", height=140)
        ftype = st.selectbox("Format", ["reel", "carousel", "image"])
        submitted = st.form_submit_button("🔮 Prognose erstellen", width="stretch")

    if not submitted:
        return
    if not draft.strip():
        st.warning("Bitte einen Entwurf eingeben.")
        return

    with st.spinner("Claude prognostiziert …"):
        f = forecast_post(profile["username"], draft, post_type=ftype, platform=profile.get("platform"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Prognose-Rating", f["predicted_rating"].upper(), help=_RATING_HELP)
    c2.metric("Erwartete ER", f"~{f['predicted_er_range']}")
    c3.metric("Konfidenz", f["confidence"])

    st.markdown(f"**Begründung:** {f['reasoning']}")
    st.markdown("**Verbesserungen:**")
    for i in f["improvements"]:
        st.markdown(f"- {i}")

    st.success(f"**Optimierter Hook:** {f['optimized_hook']}")
    if f.get("optimized_caption"):
        st.markdown(f"**Optimierte Caption:**  \n{f['optimized_caption']}")
    st.markdown(f"**Bester Zeitpunkt:** {f['best_time']}")
