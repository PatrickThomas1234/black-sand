"""Lese-Helfer für Auswertungen/Dashboard.

Lädt Posts + jüngste Metriken + Performance-Scores eines Profils und joint sie
zu einem flachen pandas-DataFrame.
"""

from __future__ import annotations

import pandas as pd

from .db import get_client


def metric_history(username: str) -> pd.DataFrame:
    """Alle Metrik-Snapshots eines Profils (Zeitreihe), inkl. shortcode/post_type."""
    db = get_client()
    profile = get_profile(username)
    if not profile:
        return pd.DataFrame()
    posts = (
        db.table("posts")
        .select("id,platform_post_id,post_type,posted_at")
        .eq("profile_id", profile["id"])
        .execute()
        .data
    )
    if not posts:
        return pd.DataFrame()
    meta = {p["id"]: p for p in posts}
    snaps = (
        db.table("metric_snapshots")
        .select("post_id,captured_at,likes,comments,views,plays")
        .in_("post_id", list(meta))
        .order("captured_at")
        .execute()
        .data
    )
    if not snaps:
        return pd.DataFrame()
    df = pd.DataFrame(snaps)
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    df["shortcode"] = df["post_id"].map(lambda i: meta[i]["platform_post_id"])
    df["post_type"] = df["post_id"].map(lambda i: meta[i]["post_type"])
    df["posted_at"] = pd.to_datetime(
        df["post_id"].map(lambda i: meta[i]["posted_at"]), utc=True, errors="coerce"
    )
    return df


def velocity_summary(username: str) -> pd.DataFrame:
    """Pro Post: jüngstes Wachstum zwischen den letzten zwei Snapshots.

    Spalten: shortcode, post_type, posted_at, n_snapshots, latest_likes,
    delta_likes, delta_hours, likes_per_day, last_captured.
    """
    hist = metric_history(username)
    if hist.empty:
        return pd.DataFrame()

    rows = []
    for post_id, g in hist.groupby("post_id"):
        g = g.sort_values("captured_at")
        last = g.iloc[-1]
        n = len(g)
        delta_likes = delta_hours = likes_per_day = None
        if n >= 2:
            prev = g.iloc[-2]
            delta_likes = (last["likes"] or 0) - (prev["likes"] or 0)
            dh = (last["captured_at"] - prev["captured_at"]).total_seconds() / 3600
            delta_hours = round(dh, 1)
            if dh > 0:
                likes_per_day = round(delta_likes / dh * 24, 1)
        rows.append(
            {
                "shortcode": last["shortcode"],
                "post_type": last["post_type"],
                "posted_at": last["posted_at"],
                "n_snapshots": n,
                "latest_likes": last["likes"],
                "delta_likes": delta_likes,
                "delta_hours": delta_hours,
                "likes_per_day": likes_per_day,
                "last_captured": last["captured_at"],
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("posted_at", ascending=False).reset_index(drop=True)


def list_profiles() -> list[dict]:
    db = get_client()
    return (
        db.table("profiles")
        .select("id,username,full_name,platform,follower_count,post_count")
        .order("username")
        .execute()
        .data
    )


def get_profile(username: str) -> dict | None:
    db = get_client()
    rows = (
        db.table("profiles")
        .select("*")
        .eq("username", username.strip().lstrip("@"))
        .execute()
        .data
    )
    return rows[0] if rows else None


def profile_dataframe(username: str) -> pd.DataFrame:
    """Ein DataFrame pro Post: Stammdaten + jüngste Metriken + Score."""
    db = get_client()
    profile = get_profile(username)
    if not profile:
        return pd.DataFrame()

    posts = (
        db.table("posts")
        .select(
            "id,platform_post_id,post_type,caption,url,posted_at,is_video,"
            "hashtags,music,tagged_usernames"
        )
        .eq("profile_id", profile["id"])
        .execute()
        .data
    )
    if not posts:
        return pd.DataFrame()
    ids = [p["id"] for p in posts]

    # jüngster Metrik-Snapshot pro Post
    snaps = (
        db.table("metric_snapshots")
        .select("post_id,likes,comments,views,plays,captured_at")
        .in_("post_id", ids)
        .order("captured_at", desc=True)
        .execute()
        .data
    )
    latest_metric: dict[str, dict] = {}
    for s in snaps:
        latest_metric.setdefault(s["post_id"], s)

    # jüngster Score pro Post
    scores = (
        db.table("performance_scores")
        .select("post_id,engagement_rate,baseline_zscore,rating,computed_at,details")
        .in_("post_id", ids)
        .order("computed_at", desc=True)
        .execute()
        .data
    )
    latest_score: dict[str, dict] = {}
    for s in scores:
        latest_score.setdefault(s["post_id"], s)

    # Transkripte + LLM-Analyse
    tr = db.table("transcripts").select("post_id,text").in_("post_id", ids).execute().data
    tr_by = {t["post_id"]: t["text"] for t in tr}
    an = (
        db.table("content_analysis")
        .select("post_id,analysis")
        .in_("post_id", ids)
        .execute()
        .data
    )
    an_by = {a["post_id"]: a["analysis"] for a in an}

    records = []
    for p in posts:
        m = latest_metric.get(p["id"], {})
        sc = latest_score.get(p["id"], {})
        records.append(
            {
                "shortcode": p["platform_post_id"],
                "post_type": p["post_type"],
                "is_video": p["is_video"],
                "posted_at": p["posted_at"],
                "caption": (p["caption"] or "").replace("\n", " "),
                "url": p["url"],
                "likes": m.get("likes"),
                "comments": m.get("comments"),
                "views": m.get("views"),
                "engagement_rate": sc.get("engagement_rate"),
                "zscore": sc.get("baseline_zscore"),
                "rating": sc.get("rating"),
                "transcript": tr_by.get(p["id"]),
                "analysis": an_by.get(p["id"]),
                "hashtag_count": len(p.get("hashtags") or []),
                "tagged_count": len(p.get("tagged_usernames") or []),
                "uses_original_audio": (p.get("music") or {}).get("uses_original_audio"),
                "caption_length": len(p.get("caption") or ""),
            }
        )

    df = pd.DataFrame(records)
    if not df.empty:
        df["posted_at"] = pd.to_datetime(df["posted_at"], utc=True, errors="coerce")
        df = df.sort_values("posted_at", ascending=False).reset_index(drop=True)
    return df


# Zeitzone des Creators (für Wochentag/Uhrzeit-Muster). Später pro Profil konfigurierbar.
_LOCAL_TZ = "Europe/Berlin"
_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _grp(df: pd.DataFrame, by: str) -> list[dict]:
    """avg z-Score + avg ER + n je Gruppe, nach z absteigend."""
    g = (
        df.dropna(subset=["zscore"])
        .groupby(by, dropna=True)
        .agg(n=("zscore", "size"), avg_z=("zscore", "mean"), avg_er=("engagement_rate", "mean"))
        .reset_index()
    )
    g = g[g["n"] >= 1].sort_values("avg_z", ascending=False)
    return [
        {
            str(by): (r[by].item() if hasattr(r[by], "item") else r[by]),
            "n": int(r["n"]),
            "avg_z": round(float(r["avg_z"]), 3),
            "avg_er": round(float(r["avg_er"]), 3),
        }
        for _, r in g.iterrows()
    ]


def feature_aggregates(username: str) -> dict:
    """Datengetriebene Muster eines Profils — Basis für Playbook & Forecast."""
    df = profile_dataframe(username)
    if df.empty:
        return {}

    d = df.copy()
    local = d["posted_at"].dt.tz_convert(_LOCAL_TZ)
    d["weekday"] = local.dt.weekday.map(lambda i: _WEEKDAYS[i] if pd.notna(i) else None)
    d["hour_bucket"] = pd.cut(
        local.dt.hour,
        bins=[-1, 6, 11, 14, 18, 21, 24],
        labels=["Nacht", "Vormittag", "Mittag", "Nachmittag", "Abend", "Spätabend"],
    )
    d["audio"] = d["uses_original_audio"].map(
        {True: "Original-Audio", False: "Trending/Fremd-Sound"}
    )
    d["caption_len_bucket"] = pd.cut(
        d["caption_length"],
        bins=[-1, 80, 200, 500, 100000],
        labels=["sehr kurz (<80)", "kurz (80-200)", "mittel (200-500)", "lang (>500)"],
    )
    d["hashtag_bucket"] = pd.cut(
        d["hashtag_count"],
        bins=[-1, 0, 3, 6, 100],
        labels=["keine", "1-3", "4-6", "7+"],
    )

    # content_format aus der LLM-Analyse
    d["format_llm"] = d["analysis"].map(
        lambda a: a.get("content_format") if isinstance(a, dict) else None
    )

    # Top-Themen über alle Posts (explodiert)
    topic_rows = []
    for _, r in d.dropna(subset=["zscore"]).iterrows():
        a = r["analysis"]
        if isinstance(a, dict):
            for t in a.get("topics", []) or []:
                topic_rows.append({"topic": t, "zscore": r["zscore"]})
    topics = []
    if topic_rows:
        td = pd.DataFrame(topic_rows)
        tg = (
            td.groupby("topic")
            .agg(n=("zscore", "size"), avg_z=("zscore", "mean"))
            .reset_index()
        )
        tg = tg[tg["n"] >= 2].sort_values("avg_z", ascending=False)
        topics = [
            {"topic": r["topic"], "n": int(r["n"]), "avg_z": round(float(r["avg_z"]), 3)}
            for _, r in tg.iterrows()
        ]

    def _post_brief(r: pd.Series) -> dict:
        a = r["analysis"] if isinstance(r["analysis"], dict) else {}
        return {
            "shortcode": r["shortcode"],
            "rating": r["rating"],
            "z": round(float(r["zscore"]), 2) if pd.notna(r["zscore"]) else None,
            "post_type": r["post_type"],
            "format": a.get("content_format"),
            "hook": a.get("hook"),
            "drivers": a.get("performance_drivers", []),
        }

    ranked = d.dropna(subset=["zscore"]).sort_values("zscore", ascending=False)
    reels = d[d["post_type"] == "reel"]

    return {
        "username": username,
        "n_posts": int(len(d)),
        "n_analyzed": int(d["analysis"].notna().sum()),
        "overall": {
            "avg_engagement_rate": round(float(d["engagement_rate"].mean(skipna=True)), 3),
            "avg_views_reels": (
                round(float(reels["views"].mean(skipna=True)), 0)
                if not reels["views"].dropna().empty
                else None
            ),
        },
        "by_format": _grp(d, "post_type"),
        "by_content_format": _grp(d.dropna(subset=["format_llm"]), "format_llm"),
        "by_audio": _grp(d.dropna(subset=["audio"]), "audio"),
        "by_weekday": _grp(d.dropna(subset=["weekday"]), "weekday"),
        "by_hour_bucket": _grp(d.dropna(subset=["hour_bucket"]), "hour_bucket"),
        "by_caption_length": _grp(d.dropna(subset=["caption_len_bucket"]), "caption_len_bucket"),
        "by_hashtag_count": _grp(d.dropna(subset=["hashtag_bucket"]), "hashtag_bucket"),
        "top_topics": topics,
        "best_posts": [_post_brief(r) for _, r in ranked.head(5).iterrows()],
        "worst_posts": [_post_brief(r) for _, r in ranked.tail(5).iterrows()],
    }
