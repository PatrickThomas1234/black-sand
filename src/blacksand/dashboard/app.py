"""Black Sand — Dashboard (Multipage).

Start:
    uv run streamlit run src/blacksand/dashboard/app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Blacksand", page_icon="🏖️", layout="wide")

from blacksand.dashboard.pages_ import (  # noqa: E402
    audience,
    competitors,
    forecast,
    generator,
    model_eval,
    niche,
    overview,
    planner,
    playbook,
    posts,
    radar,
    transcripts,
    trends,
)
from blacksand.dashboard.auth import require_login  # noqa: E402
from blacksand.dashboard.shared import sidebar_context  # noqa: E402

# Login-Gate (nur aktiv, wenn DASHBOARD_PASSWORD gesetzt ist)
require_login()

# Globaler Plattform-/Account-Wähler (in der Sidebar, vor der Navigation)
sidebar_context()

nav = st.navigation(
    [
        st.Page(overview.render, title="Übersicht", icon="📊", url_path="overview", default=True),
        st.Page(posts.render, title="Posts", icon="📑", url_path="posts"),
        st.Page(audience.render, title="Publikum", icon="💬", url_path="audience"),
        st.Page(playbook.render, title="Playbook", icon="🎯", url_path="playbook"),
        st.Page(forecast.render, title="Forecast", icon="🔮", url_path="forecast"),
        st.Page(generator.render, title="Generator", icon="✍️", url_path="generator"),
        st.Page(planner.render, title="Kalender", icon="🗓️", url_path="planner"),
        st.Page(model_eval.render, title="Modellgüte", icon="🧪", url_path="model"),
        st.Page(trends.render, title="Trends & Hype", icon="📈", url_path="trends"),
        st.Page(competitors.render, title="Konkurrenz", icon="🏆", url_path="competitors"),
        st.Page(niche.render, title="Nische", icon="🌍", url_path="niche"),
        st.Page(radar.render, title="Trend-Radar", icon="🧭", url_path="radar"),
        st.Page(transcripts.render, title="Transkripte", icon="📚", url_path="transcripts"),
    ]
)
nav.run()
