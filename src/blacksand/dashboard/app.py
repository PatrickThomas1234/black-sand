"""Black Sand — Dashboard (Multipage).

Start:
    uv run streamlit run src/blacksand/dashboard/app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Black Sand", page_icon="🏖️", layout="wide")

from blacksand.dashboard.pages_ import (  # noqa: E402
    forecast,
    overview,
    playbook,
    posts,
    transcripts,
)
from blacksand.dashboard.shared import sidebar_context  # noqa: E402

# Globaler Plattform-/Account-Wähler (in der Sidebar, vor der Navigation)
sidebar_context()

nav = st.navigation(
    [
        st.Page(overview.render, title="Übersicht", icon="📊", url_path="overview", default=True),
        st.Page(posts.render, title="Posts", icon="📑", url_path="posts"),
        st.Page(playbook.render, title="Playbook", icon="🎯", url_path="playbook"),
        st.Page(forecast.render, title="Forecast", icon="🔮", url_path="forecast"),
        st.Page(transcripts.render, title="Transkripte", icon="📚", url_path="transcripts"),
    ]
)
nav.run()
