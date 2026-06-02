"""Semantische Post-Embeddings + Ähnlichkeits-Prognose (pgvector).

Jeder Post wird aus Caption + Transkript + visueller Zusammenfassung in einen
384-dim-Vektor übersetzt (lokales mehrsprachiges Modell via fastembed, kein
API-Key). Gespeichert in post_embeddings (Supabase pgvector).

Damit lässt sich ein Entwurf den ähnlichsten vergangenen Posts (eigener Kanal +
Nische + Konkurrenz) zuordnen → datenbasierte Prognose ("zu 92 % wie dieser
virale Post").
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .db import get_client, run_sql

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384


@lru_cache
def _model():
    from fastembed import TextEmbedding

    print(f"→ Lade Embedding-Modell '{MODEL}' (einmaliger Download beim ersten Mal) …")
    return TextEmbedding(model_name=MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    return [[float(x) for x in v] for v in _model().embed(list(texts))]


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def _post_text(caption: str | None, transcript: str | None, visual: str | None) -> str:
    parts = []
    if caption:
        parts.append(caption.strip())
    if transcript:
        parts.append(transcript.strip()[:1500])
    if visual:
        parts.append(visual.strip())
    return "\n".join(parts).strip() or "(kein Text)"


def index_profile(username: str, redo: bool = False, platform: str | None = None) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    pq = db.table("profiles").select("id").eq("username", username)
    if platform:
        pq = pq.eq("platform", platform)
    prof = pq.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    posts = db.table("posts").select("id,caption").eq("profile_id", prof[0]["id"]).execute().data
    ids = [p["id"] for p in posts]
    if not ids:
        return {"profile": username, "indexed": 0}

    if not redo:
        done = {e["post_id"] for e in db.table("post_embeddings").select("post_id").in_("post_id", ids).execute().data}
        posts = [p for p in posts if p["id"] not in done]
    if not posts:
        print(f"  @{username}: bereits indexiert.")
        return {"profile": username, "indexed": 0}

    ids = [p["id"] for p in posts]
    tr = {t["post_id"]: t["text"] for t in db.table("transcripts").select("post_id,text").in_("post_id", ids).execute().data}
    vis = {v["post_id"]: (v["payload"] or {}).get("visual_summary")
           for v in db.table("visual_analysis").select("post_id,payload").in_("post_id", ids).execute().data}

    texts = [_post_text(p.get("caption"), tr.get(p["id"]), vis.get(p["id"])) for p in posts]
    vecs = embed(texts)

    # chunkweise per Management-API upserten (Vector-Cast)
    rows = [f"('{p['id']}'::uuid, '{MODEL}', '{_vec_literal(v)}'::vector)"
            for p, v in zip(posts, vecs)]
    for i in range(0, len(rows), 100):
        chunk = ",".join(rows[i:i + 100])
        run_sql(
            f"insert into post_embeddings (post_id, model, embedding) values {chunk} "
            "on conflict (post_id) do update set embedding = excluded.embedding, "
            "model = excluded.model, created_at = now();"
        )
    print(f"  @{username}: {len(posts)} Posts embedded.")
    return {"profile": username, "indexed": len(posts)}


def index_all(redo: bool = False) -> list[dict[str, Any]]:
    db = get_client()
    out = []
    for p in db.table("profiles").select("username,platform").execute().data:
        try:
            out.append(index_profile(p["username"], redo=redo, platform=p["platform"]))
        except Exception as e:  # noqa: BLE001
            print(f"  FEHLER @{p['username']} ({p['platform']}): {e}")
    return out


def similar_to_text(text: str, k: int = 8) -> list[dict[str, Any]]:
    """Die k ähnlichsten bereits indexierten Posts (über alle Profile)."""
    vec = _vec_literal(embed([text])[0])
    sql = f"""
        select pr.username, pr.role, p.post_type, p.caption,
               ps.rating, ps.engagement_rate,
               round((1 - (pe.embedding <=> '{vec}'::vector))::numeric, 3) as similarity
        from post_embeddings pe
        join posts p on p.id = pe.post_id
        join profiles pr on pr.id = p.profile_id
        left join performance_scores ps on ps.post_id = pe.post_id
        order by pe.embedding <=> '{vec}'::vector
        limit {int(k)};
    """
    rows = run_sql(sql)
    # Management-API liefert i.d.R. eine Liste von Dicts
    return rows if isinstance(rows, list) else []
