"""Seite: Transkripte — Suche, Download, Gesamtansicht."""

from __future__ import annotations

import streamlit as st

from blacksand.dashboard.shared import require_df, require_profile


def render() -> None:
    profile = require_profile()
    df = require_df(profile)
    st.title("📚 Transkripte")
    st.caption("Der komplette gesprochene Inhalt deiner Videos — durchsuchbar und als Download.")

    tmask = df["transcript"].notna() & df["transcript"].fillna("").str.strip().ne("")
    tdf = df[tmask].sort_values("posted_at", ascending=False)

    if tdf.empty:
        st.info("Für dieses Profil liegen keine Transkripte vor "
                f"(`uv run bs-transcribe {profile['username']}` für Reels mit Sprache).")
        st.stop()

    doc_lines = [f"# Gesamttranskript — @{profile['username']}", ""]
    for i, (_, r) in enumerate(tdf.iterrows(), 1):
        date = str(r["posted_at"])[:10]
        doc_lines += [
            f"## {i}. {r['shortcode']} · {r['post_type']} · {date} · Rating {r['rating'] or '—'}",
            r["url"] or "", "", (r["transcript"] or "").strip(), "", "---", "",
        ]
    doc = "\n".join(doc_lines)

    n_video = int((df["is_video"] == True).sum())  # noqa: E712
    c_l, c_r = st.columns([3, 1])
    c_l.caption(f"{len(tdf)} Reels mit gesprochenem Text "
                f"(von {n_video} Videos · {n_video - len(tdf)} ohne Sprache).")
    c_r.download_button(
        "⬇️ Als Markdown", doc,
        file_name=f"transkripte_{profile['username']}.md",
        mime="text/markdown", width="stretch",
    )

    search = st.text_input("🔎 In Transkripten suchen",
                           placeholder="z.B. Sponsor, Monaco, Qualifying …")
    shown = 0
    for _, r in tdf.iterrows():
        text = (r["transcript"] or "").strip()
        if search and search.lower() not in text.lower() \
                and search.lower() not in (r["caption"] or "").lower():
            continue
        shown += 1
        date = str(r["posted_at"])[:10]
        with st.expander(f"[{r['rating'] or '—'}] {r['post_type']} · {date} · {(r['caption'] or '')[:60]}"):
            if r["url"]:
                st.markdown(f"[→ Auf Instagram öffnen]({r['url']})")
            st.write(text)
    if search and shown == 0:
        st.warning(f"Kein Transkript enthält „{search}“.")
