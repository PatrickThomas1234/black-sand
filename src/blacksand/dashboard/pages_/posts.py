"""Seite: Posts — filterbare Tabelle + Detailansicht (Insights + Transkript)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import altair as alt

from blacksand.analytics import metric_history
from blacksand.dashboard.shared import RATING_ORDER, SCORE_HELP, require_df, require_profile


def render() -> None:
    profile = require_profile()
    df = require_df(profile)
    st.title("📑 Posts")
    st.caption("Jeder einzelne Post mit Score, Reichweite, Transkript, visueller Analyse "
               "und KI-Insights — filter- und durchsuchbar.")

    # Filter
    fc1, fc2 = st.columns(2)
    types = sorted(t for t in df["post_type"].dropna().unique())
    sel_types = fc1.multiselect("Post-Typ", types, default=types)
    ratings = [r for r in RATING_ORDER if r in df["rating"].dropna().unique()]
    sel_ratings = fc2.multiselect("Rating", ratings, default=ratings)

    fdf = df[df["post_type"].isin(sel_types)]
    if sel_ratings:
        fdf = fdf[fdf["rating"].isin(sel_ratings)]

    if fdf.empty:
        st.warning("Keine Posts für die aktuelle Filterauswahl.")
        st.stop()

    st.dataframe(
        fdf[["rating", "zscore", "engagement_rate", "post_type", "likes",
             "comments", "views", "posted_at", "caption", "url"]],
        width="stretch",
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("Link", display_text="open"),
            "posted_at": st.column_config.DatetimeColumn("Datum", format="DD.MM.YYYY"),
            "engagement_rate": st.column_config.NumberColumn(
                "ER %", help="Engagement-Rate = (Likes + Kommentare) ÷ Follower × 100", format="%.2f"
            ),
            "zscore": st.column_config.NumberColumn("Score", help=SCORE_HELP, format="%+.2f"),
            "rating": st.column_config.TextColumn("Rating", help="Einordnung des Scores: viral / good / avg / below / flop"),
            "caption": st.column_config.TextColumn("Caption", width="large"),
        },
    )

    st.divider()
    st.subheader("🔍 Post-Detail")
    n_analyzed = fdf["analysis"].notna().sum()
    n_transcribed = fdf["transcript"].notna().sum()
    st.caption(f"{n_analyzed}/{len(fdf)} analysiert · {n_transcribed}/{len(fdf)} transkribiert")

    labeled = fdf.copy()
    labeled["_label"] = [
        f"[{r['rating'] or '—'}] {r['post_type']} · {(r['caption'] or '')[:55]}"
        for _, r in labeled.iterrows()
    ]
    choice = st.selectbox("Post wählen", labeled["_label"].tolist())
    sel = labeled[labeled["_label"] == choice].iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Rating", sel["rating"] or "—", help="Einordnung relativ zum Kanal-Schnitt.")
    k2.metric("Score", f"{sel['zscore']:+.2f}" if pd.notna(sel["zscore"]) else "—", help=SCORE_HELP)
    k3.metric("ER %", f"{sel['engagement_rate']:.2f}" if pd.notna(sel["engagement_rate"]) else "—",
              help="Engagement-Rate = (Likes + Kommentare) ÷ Follower × 100")
    views = int(sel["views"]) if pd.notna(sel["views"]) else "—"
    k4.metric("👍 / 💬 / 👁", f"{sel['likes']} / {sel['comments']} / {views}")

    if pd.notna(sel.get("view_rate")):
        st.caption(f"📡 Reichweite: {sel['view_rate']:.0f}% der Follower-Basis "
                   "(>100% = über die Follower hinaus ausgespielt → Algorithmus-Push)")

    st.markdown(f"**Caption:** {sel['caption']}")
    if sel["url"]:
        st.markdown(f"[→ Auf Instagram öffnen]({sel['url']})")

    a = sel["analysis"]
    if a:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Hook:** {a.get('hook', '')}")
            st.markdown(f"**Format:** {a.get('content_format', '')}")
            st.markdown(f"**Tonalität:** {a.get('tone', '')}")
            st.markdown(f"**CTA:** {a.get('cta', '')}")
            st.markdown(f"**Themen:** {', '.join(a.get('topics', []))}")
        with col_b:
            st.markdown("**Aufbau:**")
            for step in a.get("structure", []):
                st.markdown(f"- {step}")
        st.markdown("**📈 Warum hat der Post so performt?**")
        for d in a.get("performance_drivers", []):
            st.markdown(f"- {d}")
    else:
        st.info("Noch keine KI-Analyse für diesen Post. `uv run bs-analyze <user>`")

    v = sel.get("visual")
    if v:
        st.markdown("**👁 Visuelle Analyse** (was im Post passiert)")
        st.markdown(f"{v.get('visual_summary', '')}")
        vc1, vc2 = st.columns(2)
        with vc1:
            st.markdown(f"**Szene:** {v.get('scene', '')}")
            st.markdown(f"**Motive:** {', '.join(v.get('subjects', []))}")
            st.markdown(f"**On-Screen-Text:** {v.get('on_screen_text', '')}")
        with vc2:
            st.markdown(f"**Visueller Hook:** {v.get('visual_hook', '')}")
            st.markdown(f"**Marken:** {', '.join(v.get('branding', [])) or '—'}")
            st.markdown(f"**Stimmung:** {v.get('mood', '')}")

    if sel["transcript"]:
        with st.expander("📝 Transkript anzeigen"):
            st.write(sel["transcript"])
    elif sel["is_video"]:
        st.caption("📝 Transkript noch nicht verfügbar.")

    # Metrik-Verlauf (Velocity) des gewählten Posts
    hist = metric_history(profile["username"], profile.get("platform"))
    if not hist.empty:
        h = hist[hist["shortcode"] == sel["shortcode"]]
        if len(h) >= 2:
            st.markdown("**📈 Metrik-Verlauf**")
            mh = h.melt(
                id_vars=["captured_at"],
                value_vars=["likes", "comments", "views"],
                var_name="Metrik",
                value_name="Wert",
            ).dropna(subset=["Wert"])
            st.altair_chart(
                alt.Chart(mh).mark_line(point=True).encode(
                    x=alt.X("captured_at:T", title="Messzeitpunkt"),
                    y=alt.Y("Wert:Q"),
                    color="Metrik:N",
                    tooltip=["captured_at:T", "Metrik:N", "Wert:Q"],
                ).properties(height=240),
                width="stretch",
            )
        elif len(h) == 1:
            st.caption("📈 Nur eine Messung — für einen Verlauf `uv run bs-refresh` wiederholen.")
