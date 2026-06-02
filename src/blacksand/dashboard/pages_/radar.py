"""Seite: Trend-Radar — was in der Nische gerade aufsteigt."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from blacksand.dashboard.shared import require_profile
from blacksand.radar import niche_radar


@st.cache_data(ttl=300)
def _radar(username: str, platform: str | None, days: int) -> dict:
    return niche_radar(username, platform, recent_days=days)


def render() -> None:
    profile = require_profile()
    st.title("🧭 Trend-Radar")
    st.caption("Was in deiner Nische (eigener Account + Konkurrenten) gerade aufsteigt — "
               "Engagement-Momentum der jüngsten Periode vs. davor. Ziel: Trends früh adaptieren.")

    days = st.slider("Jüngste Periode (Tage)", 14, 90, 45, step=7)
    r = _radar(profile["username"], profile.get("platform"), days)
    if not r:
        st.info("Noch keine Nische-Daten. Erst Konkurrenten erfassen "
                f"(`uv run bs-competitors {profile['username']}`).")
        st.stop()

    st.caption(f"{r['n_recent']} Posts in den letzten {r['recent_days']} Tagen.  "
               "Trend: ↑ steigend · → stabil · ↓ fallend · 🆕 neu.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔥 Heiße Hashtags** (Ø ER zuletzt)")
        for h in r["hot_hashtags"]:
            st.markdown(f"- {h['trend']} **#{h['hashtag']}** · ER {h['recent_er']} (n={h['recent_n']})")
    with col2:
        st.markdown("**🎬 Formate**")
        for f in r["hot_formats"]:
            st.markdown(f"- {f['trend']} **{f['format']}** · ER {f['recent_er']} (n={f['recent_n']})")

    st.divider()
    st.markdown("**📈 Aufsteigende Accounts** (Engagement-Momentum)")
    sa = pd.DataFrame(r["surging_accounts"])
    if sa.empty:
        st.caption("Zu wenig Verlaufsdaten für Momentum.")
    else:
        st.dataframe(
            sa, width="stretch", hide_index=True,
            column_config={
                "account": st.column_config.TextColumn("Account"),
                "older_er": st.column_config.NumberColumn("ER früher", format="%.2f"),
                "recent_er": st.column_config.NumberColumn("ER zuletzt", format="%.2f"),
                "change_pct": st.column_config.NumberColumn("Veränderung", format="%+d%%"),
            },
        )
        st.caption("Stark steigende Accounts lohnt es sich genau anzuschauen — was machen die gerade anders?")
