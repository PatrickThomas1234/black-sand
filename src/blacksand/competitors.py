"""Build C-2 — relevanzbasierte Konkurrenz-Erkennung.

Ablauf:
  1. Nische-Signatur aus den eigenen Daten ableiten (stärkste Hashtags).
  2. Per Apify-Hashtag-Suche aktuelle Posts zu diesen Hashtags ziehen.
  3. Die Profile dahinter sammeln und nach Relevanz ranken (wie oft sie in der
     Nische auftauchen, über wie viele der Hashtags).
  4. Top-N ingesten (+ scoren) und die Konkurrenz-Liste am Account speichern.

So passen die Konkurrenten automatisch zu Content UND Zielgruppe des Accounts.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from . import apify
from .config import get_settings
from .db import get_client
from .ingest import ingest_profile
from .llm import tool_call
from .scoring import score_profile

# generische/markenbezogene Tags, die als Nische-Signal wenig taugen
_STOP_HASHTAGS = {
    "weihnachten", "nachhaltigkeit", "energie", "werbung", "anzeige",
    "sponsoring", "sponsor", "sponsored", "ad", "werbungunbezahlt",
}
# generische Wörter, die nicht als Themen-Token zählen sollen
_STOP_TOKENS = {"sponsoring", "motivation", "aufholjagd", "anzeige", "werbung",
                "energy", "elite", "energie"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def niche_hashtags(username: str, k: int = 4, platform: str | None = None) -> list[str]:
    """Disziplin-/Nische-Hashtags: Account-Hashtags, die durch die analysierten
    Content-Themen bestätigt werden (filtert Personen-/Team-/Sponsor-Tags raus).
    Fallback: slugifizierte Top-Themen."""
    db = get_client()
    pq = db.table("profiles").select("id").eq("username", username)
    if platform:
        pq = pq.eq("platform", platform)
    prof = pq.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")
    profile_id = prof[0]["id"]

    posts = db.table("posts").select("id,hashtags").eq("profile_id", profile_id).execute().data
    ids = [p["id"] for p in posts]
    analyses = (
        db.table("content_analysis").select("analysis").in_("post_id", ids).execute().data
        if ids else []
    )

    # Themen → Tokens (≥4 Zeichen) + Slugs
    topic_counts: Counter = Counter()
    topic_tokens: set[str] = set()
    topic_slugs: set[str] = set()
    for a in analyses:
        for t in (a["analysis"].get("topics") or []):
            topic_counts[t] += 1
            topic_slugs.add(_slug(t))
            for tok in re.split(r"\s+", t.lower()):
                tok = re.sub(r"[^a-z0-9]", "", tok)
                if len(tok) >= 4 and tok not in _STOP_TOKENS:
                    topic_tokens.add(tok)

    # Namens-Tokens (≥4) aus dem Username, um Personen-Tags auszuschließen
    name_tokens = {t for t in re.split(r"[^a-z]+", username.lower()) if len(t) >= 4}

    ht_set: set[str] = set()
    for p in posts:
        for h in (p.get("hashtags") or []):
            ht_set.add(h.lower())

    def _score(h: str) -> int:
        # wie viele Themen-Tokens stecken im Hashtag + Bonus für exakten Themen-Slug
        n = sum(1 for tok in topic_tokens if tok in h)
        return n + (1 if h in topic_slugs else 0)

    def _eligible(h: str) -> bool:
        if h in _STOP_HASHTAGS:
            return False
        if any(nt in h for nt in name_tokens):  # Personen-Marke raus
            return False
        return _score(h) > 0

    scored = sorted(
        ((h, _score(h)) for h in ht_set if _eligible(h)),
        key=lambda x: (-x[1], len(x[0])),
    )
    kept = [h for h, _ in scored]

    # Fallback: slugifizierte Top-Themen, falls keine passenden Account-Hashtags
    if not kept:
        kept = [
            _slug(t) for t, _ in topic_counts.most_common()
            if 3 <= len(_slug(t)) <= 30 and not any(nt in _slug(t) for nt in name_tokens)
        ]

    # Near-Duplikate entzerren (porschecarreracup vs ...deutschland), höheren Score behalten
    out: list[str] = []
    for h in kept:
        if not any(h in o or o in h for o in out):
            out.append(h)
        if len(out) >= k:
            break
    return out


def _owner_of(item: dict, platform: str) -> tuple[str | None, dict]:
    """(owner_username, owner_meta) je Plattform aus einem Hashtag-Post-Item."""
    if platform == "tiktok":
        a = item.get("authorMeta") or {}
        return a.get("name"), {
            "followers": a.get("fans"), "bio": a.get("signature"),
            "verified": a.get("verified"), "nick": a.get("nickName"),
        }
    return item.get("ownerUsername"), {}


def _engagement_of(item: dict, platform: str) -> int:
    if platform == "tiktok":
        return (item.get("diggCount") or 0) + (item.get("commentCount") or 0)
    return (item.get("likesCount") or 0) + (item.get("commentsCount") or 0)


def discover_competitors(
    username: str, per_tag: int = 30, top_n: int = 5,
    hashtags: list[str] | None = None, platform: str = "instagram",
) -> dict[str, Any]:
    username = username.strip().lstrip("@")
    tags = hashtags or niche_hashtags(username, platform=platform)
    if not tags:
        raise RuntimeError("Keine Nische-Hashtags ableitbar — erst Posts ingesten.")

    scrape = apify.scrape_tiktok_hashtag if platform == "tiktok" else apify.scrape_hashtag

    owner_count: Counter = Counter()
    owner_tags: dict[str, set] = defaultdict(set)
    owner_engagement: dict[str, int] = defaultdict(int)
    owner_meta: dict[str, dict] = {}
    for tag in tags:
        print(f"→ Hashtag #{tag} …")
        try:
            items = scrape(tag, limit=per_tag)
        except Exception as e:  # noqa: BLE001
            print(f"  FEHLER #{tag}: {e}")
            continue
        for it in items:
            ow, meta = _owner_of(it, platform)
            if not ow or ow.strip().lower() == username.lower():
                continue
            owner_count[ow] += 1
            owner_tags[ow].add(tag)
            owner_engagement[ow] += _engagement_of(it, platform)
            if meta and ow not in owner_meta:
                owner_meta[ow] = meta

    ranked = [
        {
            "username": o,
            "appearances": c,
            "n_hashtags": len(owner_tags[o]),
            "hashtags": sorted(owner_tags[o]),
            "engagement_seen": owner_engagement[o],
            "meta": owner_meta.get(o, {}),
        }
        for o, c in sorted(
            owner_count.items(),
            key=lambda kv: (len(owner_tags[kv[0]]), kv[1], owner_engagement[kv[0]]),
            reverse=True,
        )
    ]
    return {"hashtags": tags, "ranked": ranked, "top": ranked[:top_n], "platform": platform}


def _niche_context(username: str, platform: str | None = None) -> str:
    """Kurze Nische-Beschreibung des Ziel-Accounts (für die Relevanz-Klassifizierung)."""
    db = get_client()
    pq = db.table("profiles").select("id,biography").eq("username", username)
    if platform:
        pq = pq.eq("platform", platform)
    prof = pq.execute().data
    bio = (prof[0].get("biography") if prof else "") or ""
    ids = [p["id"] for p in db.table("posts").select("id").eq("profile_id", prof[0]["id"]).execute().data] if prof else []
    topics: Counter = Counter()
    if ids:
        for a in db.table("content_analysis").select("analysis").in_("post_id", ids).execute().data:
            for t in (a["analysis"].get("topics") or []):
                topics[t] += 1
    top = ", ".join(t for t, _ in topics.most_common(8))
    return f"Bio: {bio[:200]}\nHaupt-Themen: {top}"


def _est_er(details: dict) -> float | None:
    """Grobe Engagement-Rate aus den latestPosts eines Profils."""
    fc = details.get("followersCount") or 0
    posts = [p for p in (details.get("latestPosts") or []) if isinstance(p, dict)]
    if not fc or not posts:
        return None
    ers = [((p.get("likesCount") or 0) + (p.get("commentsCount") or 0)) / fc * 100 for p in posts]
    return round(mean(ers), 2) if ers else None


_CLASSIFY_TOOL = {
    "name": "classify_account",
    "description": "Klassifiziert, ob ein Account ein echter Nische-Wettbewerber ist.",
    "input_schema": {
        "type": "object",
        "properties": {
            "account_type": {
                "type": "string",
                "enum": ["creator", "athlete", "team", "brand", "media", "fan", "other"],
                "description": "Art des Accounts.",
            },
            "niche_relevant": {"type": "boolean", "description": "Macht denselben Content für dieselbe Zielgruppe?"},
            "is_competitor": {"type": "boolean", "description": "Echter inhaltlicher Wettbewerber (kein Sponsor/Marke/Medium/Fan)?"},
            "region": {"type": "string", "description": "Land/Region, falls erkennbar (sonst 'unbekannt')."},
            "reason": {"type": "string", "description": "Kurzbegründung."},
        },
        "required": ["account_type", "niche_relevant", "is_competitor", "region"],
    },
}

_CLASSIFY_SYSTEM = """Du prüfst, ob ein Instagram-Account ein echter inhaltlicher
WETTBEWERBER eines Ziel-Accounts ist (gleiche Nische, gleiche Zielgruppe) — NICHT
ein Sponsor, eine Marke, ein Medium oder ein Fan-Account. Antworte knapp auf Deutsch
und nutze IMMER das Tool classify_account."""


def _classify(username: str, details: dict, niche: str) -> dict:
    caps = [(p.get("caption") or "")[:120] for p in (details.get("latestPosts") or [])[:3] if isinstance(p, dict)]
    user = (
        f"ZIEL-NISCHE:\n{niche}\n\n"
        f"ZU PRÜFENDER ACCOUNT: @{username}\n"
        f"Name: {details.get('fullName')}\n"
        f"Kategorie: {details.get('businessCategoryName')}\n"
        f"Business-Account: {details.get('isBusinessAccount')}\n"
        f"Bio: {details.get('biography')}\n"
        f"Beispiel-Captions: {caps}"
    )
    return tool_call(_CLASSIFY_SYSTEM, user, _CLASSIFY_TOOL, max_tokens=400)


def build_competitors(
    username: str,
    top_n: int = 5,
    per_tag: int = 30,
    max_posts: int = 30,
    shortlist: int = 12,
    platform: str = "instagram",
    hashtags: list[str] | None = None,
) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    q = db.table("profiles").select("id").eq("username", username).eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} ({platform}) nicht in der DB.")

    # bestehende primäre Accounts (pro Plattform) merken, um sie NICHT herunterzustufen
    existing_primary = {
        (p["username"], p["platform"])
        for p in db.table("profiles").select("username,platform,role")
        .eq("role", "primary").execute().data
    }

    # eigene Kennzahlen als Vergleichsmaßstab (für "aspirational")
    from .analytics import profile_summary
    own = profile_summary(username, platform) or {}
    own_fc = own.get("followers") or 0
    own_er = own.get("avg_er") or 0.0
    niche = _niche_context(username, platform)

    # 1) Kandidaten finden (Hashtag-Owner, nach Relevanz/Engagement sortiert)
    disc = discover_competitors(username, per_tag=per_tag, top_n=shortlist,
                                platform=platform, hashtags=hashtags)
    cands = disc["ranked"][:shortlist]
    print(f"→ {len(cands)} Kandidaten, reichere an & klassifiziere …")

    # 2) Anreichern + 3) klassifizieren + filtern
    enriched: list[dict] = []
    for c in cands:
        u = c["username"]
        try:
            if platform == "tiktok":
                # authorMeta aus der Hashtag-Suche liefert Follower + Bio direkt
                meta = c.get("meta") or {}
                details = {
                    "fullName": meta.get("nick"),
                    "biography": meta.get("bio"),
                    "followersCount": meta.get("followers"),
                    "latestPosts": [],
                }
                er = None
            else:
                details = apify.scrape_profile(u)
                if not details:
                    continue
                er = _est_er(details)
            cls = _classify(u, details, niche)
            # Echte Nische-Wettbewerber: Creator/Fahrer/Teams — Marken/Medien/Fans raus
            if not cls.get("niche_relevant") or cls.get("account_type") not in ("creator", "athlete", "team"):
                print(f"  – @{u} verworfen ({cls.get('account_type')}, {cls.get('region')})")
                continue
            fc = details.get("followersCount")
            tier = "aspirational" if (
                (fc and own_fc and fc > own_fc) or (er and own_er and er > own_er)
            ) else ("peer" if fc and own_fc and fc >= own_fc * 0.5 else "smaller")
            enriched.append({
                "username": u, "followers": fc, "est_er": er,
                "account_type": cls.get("account_type"), "region": cls.get("region"),
                "tier": tier, "appearances": c["appearances"], "hashtags": c["hashtags"],
            })
            print(f"  ✓ @{u} · {cls.get('account_type')} · {cls.get('region')} · "
                  f"{fc} Follower · ER~{er}% · {tier}")
        except Exception as e:  # noqa: BLE001
            print(f"  FEHLER @{u}: {e}")

    # 4) Ranken: aspirational zuerst, dann höhere ER, dann mehr Follower
    tier_rank = {"aspirational": 0, "peer": 1, "smaller": 2}
    enriched.sort(key=lambda x: (
        tier_rank.get(x["tier"], 3), -(x["est_er"] or 0), -(x["followers"] or 0)
    ))
    final = enriched[:top_n]
    print(f"→ Ingeste Top-{len(final)}: {[c['username'] for c in final]}")

    # 5) Ingesten + scoren + als Konkurrent markieren
    ingested = []
    for c in final:
        u = c["username"]
        try:
            ingest_profile(u, max_posts=max_posts, platform=platform)
            score_profile(u, platform=platform)
            if (u, platform) not in existing_primary:
                db.table("profiles").update({"role": "competitor"}).eq(
                    "username", u).eq("platform", platform).execute()
            ingested.append(u)
        except Exception as e:  # noqa: BLE001
            print(f"  FEHLER @{u}: {e}")

    db.table("profile_insights").insert(
        {
            "profile_id": prof[0]["id"],
            "kind": "competitors",
            "payload": {
                "hashtags": disc["hashtags"],
                "competitors": final,
                "ingested": ingested,
                "rejected": len(cands) - len(enriched),
            },
            "aggregates": {"candidates": len(disc["ranked"]), "shortlisted": len(cands)},
            "model": get_settings().anthropic_model,
        }
    ).execute()
    return {"hashtags": disc["hashtags"], "competitors": final, "ingested": ingested}


def latest_competitors(username: str, platform: str | None = None) -> dict | None:
    db = get_client()
    q = db.table("profiles").select("id").eq("username", username.strip().lstrip("@"))
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        return None
    rows = (
        db.table("profile_insights")
        .select("payload,created_at")
        .eq("profile_id", prof[0]["id"]).eq("kind", "competitors")
        .order("created_at", desc=True).limit(1).execute().data
    )
    return rows[0] if rows else None
