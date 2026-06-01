"""Seite: Übersicht — KPIs, Rating-Verteilung, ER-Verlauf, Top/Flop."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.analytics import velocity_summary
from blacksand.dashboard.shared import (
    RATING_ORDER,
    rating_scale,
    require_df,
    require_profile,
)


def render() -> None:
    profile = require_profile()
    df = require_df(profile)

    st.title(f"📊 Übersicht — {profile.get('full_name') or profile['username']}")
    st.caption(f"@{profile['username']} · {profile['platform']}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Follower", f"{(profile.get('follower_count') or 0):,}".replace(",", "."))
    c2.metric("Posts", len(df))
    c3.metric("Ø Engagement-Rate", f"{df['engagement_rate'].mean():.2f}%")
    c4.metric("🚀 viral", int((df["rating"] == "viral").sum()))
    c5.metric("🔻 below/flop", int(df["rating"].isin(["below", "flop"]).sum()))

    st.divider()
    left, right = st.columns([1, 2])

    with left:
        st.markdown("**Rating-Verteilung**")
        counts = (
            df["rating"].value_counts().reindex(RATING_ORDER).dropna()
            .rename_axis("rating").reset_index(name="count")
        )
        if not counts.empty:
            st.altair_chart(
                alt.Chart(counts).mark_bar().encode(
                    x=alt.X("rating:N", sort=RATING_ORDER, title=None),
                    y=alt.Y("count:Q", title="Posts"),
                    color=alt.Color("rating:N", scale=rating_scale(), legend=None),
                ).properties(height=280),
                width="stretch",
            )

    with right:
        st.markdown("**Engagement-Rate über Zeit**")
        ts = df.dropna(subset=["posted_at", "engagement_rate"])[
            ["posted_at", "engagement_rate", "rating", "views", "shortcode",
             "post_type", "likes", "comments"]
        ]
        if not ts.empty:
            st.altair_chart(
                alt.Chart(ts).mark_circle(size=90).encode(
                    x=alt.X("posted_at:T", title="Datum"),
                    y=alt.Y("engagement_rate:Q", title="ER %"),
                    color=alt.Color("rating:N", scale=rating_scale(), title="Rating"),
                    size=alt.Size("views:Q", legend=None),
                    tooltip=["shortcode", "post_type", "rating", "engagement_rate",
                             "likes", "comments", "views"],
                ).properties(height=280).interactive(),
                width="stretch",
            )

    st.divider()
    col_top, col_flop = st.columns(2)
    ranked = df.dropna(subset=["zscore"]).sort_values("zscore", ascending=False)

    with col_top:
        st.markdown("**🚀 Top 5**")
        for _, r in ranked.head(5).iterrows():
            _post_line(r)
    with col_flop:
        st.markdown("**🔻 Schwächste 5**")
        for _, r in ranked.tail(5).iloc[::-1].iterrows():
            _post_line(r)

    st.divider()
    st.markdown("**📈 Engagement-Velocity**")
    vs = velocity_summary(profile["username"])
    if vs.empty:
        st.caption("Noch keine Metriken erfasst.")
    else:
        last = vs["last_captured"].max()
        last_str = last.strftime("%d.%m.%Y %H:%M") if pd.notna(last) else "—"
        st.caption(f"Letzte Messung: {last_str} · {len(vs)} Posts beobachtet")
        multi = vs[vs["n_snapshots"] >= 2].dropna(subset=["likes_per_day"])
        if multi.empty:
            st.info("Bisher nur **eine** Messung pro Post. Für echte Velocity regelmäßig "
                    "`uv run bs-refresh` ausführen (ideal per Cron alle paar Stunden) — "
                    "dann erscheint hier, welche Posts am schnellsten wachsen.")
        else:
            movers = multi.sort_values("likes_per_day", ascending=False).head(5)
            st.markdown("**Schnellste Posts (Likes/Tag seit letzter Messung):**")
            for _, r in movers.iterrows():
                st.markdown(
                    f"- **+{int(r['delta_likes'])} Likes** in {r['delta_hours']} h "
                    f"(~{r['likes_per_day']}/Tag) · {r['post_type']} · `{r['shortcode']}`"
                )


def _post_line(r: pd.Series) -> None:
    views = f" 👁{int(r['views'])}" if pd.notna(r["views"]) else ""
    st.markdown(
        f"**z={r['zscore']:.2f}** · ER {r['engagement_rate']:.2f}% · {r['post_type']} · "
        f"👍{r['likes']} 💬{r['comments']}{views}  \n_{(r['caption'] or '')[:80]}_"
    )
