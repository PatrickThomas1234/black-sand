"""Seite: Trends & Hype — Views-Geschwindigkeit als Algorithmus-Signal."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.analytics import hype_summary, metric_history
from blacksand.dashboard.shared import require_profile
from blacksand.early import early_indicator

_RICON = {"viral": "🚀", "good": "✅", "avg": "➖", "below": "🔻", "flop": "❌"}


def render() -> None:
    profile = require_profile()
    st.title("📈 Trends & Hype")
    st.caption("Views-Geschwindigkeit relativ zum Alter = wie stark der Algorithmus "
               "einen Post gerade pusht. Schärft sich mit wiederholtem `bs-refresh`.")

    hype = hype_summary(profile["username"], profile.get("platform"))
    if hype.empty:
        st.info("Noch keine Video-Metriken erfasst.")
        st.stop()

    multi = hype[hype["n_snapshots"] >= 2].dropna(subset=["views_per_day_recent"])

    st.markdown("**🔥 Zieht aktuell Aufrufe** (Tempo im letzten Mess-Intervall)")
    if multi.empty:
        st.info("Bisher nur **eine** Messung pro Post — daher kein aktuelles Tempo. "
                "`uv run bs-refresh` ein paar Mal (zeitlich versetzt) ausführen, "
                "dann erscheint hier, welche Videos gerade abheben.")
    else:
        top = multi.sort_values("views_per_day_recent", ascending=False).head(8)
        for _, r in top.iterrows():
            accel = f" · ⚡ Beschleunigung ×{r['accel']}" if pd.notna(r["accel"]) else ""
            flame = " 🔥" if pd.notna(r["accel"]) and r["accel"] and r["accel"] > 1 else ""
            st.markdown(
                f"- **~{int(r['views_per_day_recent']):,} Views/Tag**".replace(",", ".")
                + f" · {int(r['latest_views']):,} gesamt".replace(",", ".")
                + f" · {r['age_days']} Tage alt · {r['post_type']} · `{r['shortcode']}`"
                + accel + flame
            )

    st.divider()
    st.markdown("**🌱 Frühindikator** — projizierte Endperformance frischer Posts")
    st.caption("Hochrechnung aus aktuellem Engagement + Alter (Reifekurve). Am wertvollsten "
               "kurz nach dem Posten — mit regelmäßigem `bs-refresh` immer präziser.")
    early = early_indicator(profile["username"], profile.get("platform"), max_age_days=7)
    if not early:
        st.caption("Keine Posts jünger als 7 Tage.")
    else:
        for r in early:
            st.markdown(
                f"- {_RICON.get(r['projected_rating'], '?')} **{r['projected_rating']}** (proj.) · "
                f"{r['age_h']:.0f}h alt (~{r['matured_pct']}% ausgereift, Konfidenz {r['confidence']}) · "
                f"ER {r['current_er']} → proj. {r['projected_er']} · `{r['shortcode']}`"
            )

    st.divider()
    st.markdown("**📉 Aufrufe-Verlauf (Hype-Graph)**")
    hist = metric_history(profile["username"], profile.get("platform"))
    vids = hist.dropna(subset=["views"]) if not hist.empty else hist
    if vids.empty:
        st.caption("Keine Views-Daten.")
        return
    codes = vids.sort_values("posted_at", ascending=False)["shortcode"].unique().tolist()
    pick = st.selectbox("Post wählen", codes)
    h = vids[vids["shortcode"] == pick].sort_values("captured_at")
    if len(h) >= 2:
        st.altair_chart(
            alt.Chart(h).mark_line(point=True).encode(
                x=alt.X("captured_at:T", title="Messzeitpunkt"),
                y=alt.Y("views:Q", title="Views"),
                tooltip=["captured_at:T", "views:Q"],
            ).properties(height=260),
            width="stretch",
        )
    else:
        st.caption(f"Nur eine Messung für `{pick}` — für eine Kurve `bs-refresh` wiederholen.")
