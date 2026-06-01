"""Phase 2a — lokale Transkription von Reel-Videos mit faster-whisper.

Pro Video:
  1. videoUrl aus dem gespeicherten Post-Raw holen
  2. Video in eine Temp-Datei laden
  3. mit faster-whisper transkribieren (Sprache auto-detect)
  4. Text + Segmente + Sprache in `transcripts` ablegen

Das Whisper-Modell wird beim ersten Lauf einmalig heruntergeladen
(WHISPER_MODEL, Default 'small'). Läuft komplett lokal/CPU — kein API-Key.
"""

from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from .config import get_settings
from .db import get_client


@lru_cache
def _model():
    from faster_whisper import WhisperModel

    name = get_settings().whisper_model
    print(f"→ Lade Whisper-Modell '{name}' (einmaliger Download beim ersten Mal) …")
    # int8 = schnell & speicherschonend auf CPU
    return WhisperModel(name, device="cpu", compute_type="int8")


def _video_url_for(post: dict[str, Any], db) -> str | None:
    """videoUrl aus dem jüngsten Roh-Payload des Posts ziehen."""
    raw = (
        db.table("raw_payloads")
        .select("payload")
        .eq("entity_type", "post")
        .eq("entity_ref", post["platform_post_id"])
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if raw:
        return raw[0]["payload"].get("videoUrl")
    return None


def _download(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 16):
                f.write(chunk)


def transcribe_one(post: dict[str, Any], db) -> dict[str, Any] | None:
    url = _video_url_for(post, db)
    if not url:
        return None

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{post['platform_post_id']}.mp4"
        _download(url, path)
        segments, info = _model().transcribe(str(path), vad_filter=True)
        segs = [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
        ]

    text = " ".join(s["text"] for s in segs).strip()
    row = {
        "post_id": post["id"],
        "language": info.language,
        "source": f"whisper:{get_settings().whisper_model}",
        "text": text,
        "segments": segs,
    }
    db.table("transcripts").upsert(row, on_conflict="post_id").execute()
    return row


def transcribe_profile(username: str, limit: int | None = None, redo: bool = False) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")

    prof = db.table("profiles").select("id").eq("username", username).execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    posts = (
        db.table("posts")
        .select("id,platform_post_id,is_video,post_type,caption")
        .eq("profile_id", prof[0]["id"])
        .eq("is_video", True)
        .execute()
        .data
    )

    if not redo:
        done = {
            t["post_id"]
            for t in db.table("transcripts").select("post_id").execute().data
        }
        posts = [p for p in posts if p["id"] not in done]

    if limit:
        posts = posts[:limit]

    print(f"→ {len(posts)} Video(s) zu transkribieren.")
    ok = 0
    for i, p in enumerate(posts, 1):
        try:
            res = transcribe_one(p, db)
            if res:
                ok += 1
                preview = (res["text"][:70] or "(leer)").replace("\n", " ")
                print(f"  [{i}/{len(posts)}] {p['platform_post_id']} [{res['language']}]: {preview}…")
            else:
                print(f"  [{i}/{len(posts)}] {p['platform_post_id']}: keine videoUrl — übersprungen")
        except Exception as e:  # noqa: BLE001 — pro Video tolerant bleiben
            print(f"  [{i}/{len(posts)}] {p['platform_post_id']}: FEHLER {e}")

    return {"profile": username, "transcribed": ok, "attempted": len(posts)}
