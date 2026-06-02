"""Gemeinsame Helfer für die Dashboard-Seiten: Daten-Loading, Sidebar-Kontext."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.analytics import list_profiles, profile_dataframe

RATING_ORDER = ["viral", "good", "avg", "below", "flop"]
RATING_COLOR = {
    "viral": "#16a34a",
    "good": "#65a30d",
    "avg": "#a1a1aa",
    "below": "#f59e0b",
    "flop": "#dc2626",
}
PLATFORM_ICON = {"instagram": "📸", "youtube": "▶️", "linkedin": "💼", "tiktok": "🎵"}

# Einheitliche, laienverständliche Erklärung des Performance-Scores (z-Score)
SCORE_LABEL = "Score"
SCORE_HELP = (
    "Performance-Score eines Posts **relativ zum eigenen Kanal-Durchschnitt** "
    "(statistisch: z-Score in Standardabweichungen). "
    "0 = genau Durchschnitt · +1 = deutlich überdurchschnittlich · "
    "+2 = Top-Post · negativ = unter dem Schnitt. "
    "Bei Videos fließen Engagement UND Reichweite (Views/Follower) ein."
)
RATING_LEGENDE = (
    "🚀 viral (weit über Schnitt) · ✅ good (über Schnitt) · ➖ avg (Durchschnitt) · "
    "🔻 below (unter Schnitt) · ❌ flop (weit unter Schnitt) — jeweils **bezogen auf "
    "diesen Kanal**, nicht absolut."
)


@st.cache_data(ttl=60)
def get_profiles() -> list[dict]:
    # Nur eigene/primäre Accounts im Dropdown — Konkurrenten erscheinen nur
    # auf der Konkurrenz-Seite, nicht in der globalen Account-Auswahl.
    return list_profiles(role="primary")


@st.cache_data(ttl=60)
def _records(username: str, platform: str | None = None) -> list[dict]:
    return profile_dataframe(username, platform).to_dict("records")


def load_df(username: str, platform: str | None = None) -> pd.DataFrame:
    df = pd.DataFrame(_records(username, platform))
    if not df.empty:
        df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, errors="coerce")
    return df


def rating_scale() -> alt.Scale:
    return alt.Scale(domain=list(RATING_COLOR.keys()), range=list(RATING_COLOR.values()))


def sidebar_context() -> None:
    """Globaler Plattform-/Account-Wähler; legt das gewählte Profil in den State."""
    st.sidebar.title("🏖️ Black Sand")
    profiles = get_profiles()
    if not profiles:
        st.sidebar.warning("Keine Profile in der DB.\n`uv run bs-ingest <user>`")
        st.session_state["profile"] = None
        return

    platforms = sorted({p["platform"] for p in profiles})
    plat = st.sidebar.selectbox(
        "Plattform",
        platforms,
        format_func=lambda p: f"{PLATFORM_ICON.get(p, '•')} {p.capitalize()}",
    )
    accts = [p for p in profiles if p["platform"] == plat]
    labels = {f"@{p['username']}": p for p in accts}
    label = st.sidebar.selectbox("Account", list(labels.keys()))
    st.session_state["profile"] = labels[label]

    st.sidebar.divider()
    if st.sidebar.button("🔄 Daten neu laden", width="stretch"):
        st.cache_data.clear()
        st.rerun()


def current_profile() -> dict | None:
    return st.session_state.get("profile")


def require_profile() -> dict:
    """Profil aus dem State holen oder die Seite sauber beenden."""
    p = current_profile()
    if not p:
        st.info("Kein Profil ausgewählt — wähle links Plattform & Account.")
        st.stop()
    return p


def require_df(profile: dict) -> pd.DataFrame:
    df = load_df(profile["username"], profile.get("platform"))
    if df.empty:
        st.info(f"Keine Posts für @{profile['username']}. "
                f"`uv run bs-ingest {profile['username']}` ausführen.")
        st.stop()
    return df
