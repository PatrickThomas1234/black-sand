"""Seite: Konkurrenz — Benchmark vs. relevante Profile + deren aktuelle Hypes."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from blacksand.analytics import profile_dataframe, profile_summary
from blacksand.competitors import latest_competitors
from blacksand.dashboard.shared import require_profile


def render() -> None:
    profile = require_profile()
    me = profile["username"]
    st.title("🏆 Konkurrenz")
    st.caption("Benchmark gegen relevante (oft größere/internationale) Profile deiner "
               "Nische — und was bei ihnen gerade läuft.")

    comp = latest_competitors(me, profile.get("platform"))
    if not comp or not comp["payload"].get("ingested"):
        st.info(
            "Noch keine Konkurrenten erfasst. Im Terminal:\n\n"
            f"`uv run bs-competitors {me} --top 5`\n\n"
            "Das leitet relevante Nische-Hashtags aus deinen Daten ab, findet passende "
            "Profile und ingestet die Top-Treffer."
        )
        st.stop()

    tags = comp["payload"].get("hashtags", [])
    ingested = comp["payload"]["ingested"]
    meta = {c["username"]: c for c in comp["payload"].get("competitors", []) if isinstance(c, dict)}
    st.caption("Gefunden über: " + ", ".join("#" + h for h in tags))

    _TIER = {"aspirational": "🔼 aspirational", "peer": "➖ peer", "smaller": "🔽 kleiner"}

    # Benchmark-Tabelle (Account + Konkurrenten)
    rows = []
    for u in [me, *ingested]:
        s = profile_summary(u)
        if not s:
            continue
        is_me = (u == me)
        m = meta.get(u, {})
        s["ist_account"] = is_me
        s["tier"] = "🏠 eigen" if is_me else _TIER.get(m.get("tier"), "—")
        s["typ"] = "—" if is_me else (m.get("account_type") or "—")
        s["region"] = "—" if is_me else (m.get("region") or "—")
        s["_sort"] = -1 if is_me else {"aspirational": 0, "peer": 1, "smaller": 2}.get(m.get("tier"), 3)
        rows.append(s)
    bdf = pd.DataFrame(rows).sort_values("_sort")

    st.markdown("**📊 Benchmark** (aspirational = größer oder höhere ER als du — davon lernen)")
    st.dataframe(
        bdf[["username", "tier", "typ", "region", "followers", "n_posts", "avg_er", "median_er", "viral"]],
        width="stretch", hide_index=True,
        column_config={
            "username": st.column_config.TextColumn("Account"),
            "tier": st.column_config.TextColumn("Tier"),
            "typ": st.column_config.TextColumn("Typ"),
            "region": st.column_config.TextColumn("Region"),
            "followers": st.column_config.NumberColumn("Follower"),
            "n_posts": st.column_config.NumberColumn("Posts"),
            "avg_er": st.column_config.NumberColumn("Ø ER %", format="%.2f"),
            "median_er": st.column_config.NumberColumn("Median ER %", format="%.2f"),
            "viral": st.column_config.NumberColumn("🚀"),
        },
    )

    cdf = bdf.dropna(subset=["avg_er"])
    if not cdf.empty:
        st.altair_chart(
            alt.Chart(cdf).mark_bar().encode(
                x=alt.X("avg_er:Q", title="Ø Engagement-Rate %"),
                y=alt.Y("username:N", sort="-x", title=None),
                color=alt.condition(alt.datum.ist_account, alt.value("#2563eb"), alt.value("#a1a1aa")),
                tooltip=["username", "followers", "avg_er", "viral"],
            ).properties(height=40 + 32 * len(cdf)),
            width="stretch",
        )
        st.caption("Blau = dein Account. So liegst du relativ zur Nische.")

    # Aktuelle Hypes der Konkurrenz = Trends zum Adaptieren
    st.divider()
    st.markdown("**🔥 Was bei der Konkurrenz gerade läuft** (Top-Posts nach Engagement-Rate)")
    for u in ingested:
        cd = profile_summary(u)
        with st.expander(f"@{u} — Ø ER {cd['avg_er'] if cd else '—'}% · {cd['followers'] if cd else '—'} Follower"):
            d = profile_dataframe(u)
            if d.empty:
                st.caption("Keine Daten.")
                continue
            top = d.dropna(subset=["engagement_rate"]).sort_values("engagement_rate", ascending=False).head(3)
            for _, r in top.iterrows():
                views = f" · 👁{int(r['views'])}" if pd.notna(r["views"]) else ""
                st.markdown(
                    f"- **ER {r['engagement_rate']:.1f}%** · {r['post_type']} · "
                    f"👍{r['likes']} 💬{r['comments']}{views}  \n  _{(r['caption'] or '')[:90]}_"
                    + (f"  \n  [↗]({r['url']})" if r["url"] else "")
                )
