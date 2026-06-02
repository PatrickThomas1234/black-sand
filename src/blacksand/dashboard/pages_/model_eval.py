"""Seite: Modellgüte — Backtesting & Kalibrierung des Prognosemodells."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.backtest import evaluate


@st.cache_data(ttl=300)
def _eval() -> dict:
    return evaluate()


def render() -> None:
    st.title("🧪 Modellgüte")
    st.caption("Ehrliche Out-of-Fold-Bewertung des Prognosemodells (Inhalt/Embeddings → "
               "'guter Post'). Zeigt, wie verlässlich die Prognosen sind.")

    try:
        r = _eval()
    except Exception as e:  # noqa: BLE001
        st.info(f"Modell noch nicht bewertbar: {e}\n\nErst genug Posts embedden "
                "(`uv run bs-embed --all`) und scoren.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("AUC", r["auc"], help="0.5 = Zufall, >0.65 = brauchbar, >0.7 = gut")
    c2.metric("Treffer", f"{r['accuracy']:.0%}")
    c3.metric("Lift", f"{r['lift']}×" if r.get("lift") else "—",
              help="Wie viel häufiger vorhergesagte 'gute' Posts wirklich gut sind als der Schnitt")
    c4.metric("Basisrate gut", f"{r['base_rate']:.0%}")

    st.divider()
    st.markdown("**Kalibrierung** — vorhergesagte vs. tatsächliche 'gut'-Rate je Wahrscheinlichkeits-Bin")
    cal = pd.DataFrame(r["calibration"])
    if not cal.empty:
        m = cal.melt(id_vars=["bin", "n"], value_vars=["pred_mean", "actual_rate"],
                     var_name="Art", value_name="Rate")
        m["Art"] = m["Art"].map({"pred_mean": "vorhergesagt", "actual_rate": "tatsächlich"})
        st.altair_chart(
            alt.Chart(m).mark_bar().encode(
                x=alt.X("bin:N", title="Wahrscheinlichkeits-Bin"),
                xOffset="Art:N",
                y=alt.Y("Rate:Q"),
                color=alt.Color("Art:N", scale=alt.Scale(
                    domain=["vorhergesagt", "tatsächlich"], range=["#94a3b8", "#2563eb"])),
                tooltip=["bin", "n", "Rate", "Art"],
            ).properties(height=240),
            width="stretch",
        )
        st.caption("Je näher beide Balken je Bin, desto besser kalibriert.")

    st.divider()
    st.markdown("**Signal-Vergleich** — was sagt Performance am besten voraus?")
    lb = pd.DataFrame(r["leaderboard"])
    st.dataframe(lb, width="stretch", hide_index=True,
                 column_config={"signal": st.column_config.TextColumn("Signal"),
                                "metric": st.column_config.TextColumn("Maß"),
                                "value": st.column_config.NumberColumn("Wert", format="%.3f")})
    st.caption("Befund: **Inhalt/Embeddings** trägt die Vorhersage — Metadaten (Länge/Hashtags/"
               "Zeit) allein sind nicht prädiktiv (R² < 0).")
