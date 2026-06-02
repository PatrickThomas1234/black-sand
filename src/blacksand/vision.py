"""Visuelle Inhaltsanalyse mit Claude Vision.

Pro Post sammeln wir Bildmaterial und lassen Claude beschreiben, WAS visuell
passiert:
  * Bild        → das Bild selbst
  * Carousel    → die ersten Slides
  * Video/Reel  → mehrere per ffmpeg extrahierte Frames (Anfang→Ende)

Alle Bilder werden auf ~640-768px herunterskaliert (ffmpeg), um Token-Kosten zu
begrenzen. Ergebnis (Szene, On-Screen-Text, Marken, visueller Hook, Stimmung)
landet in visual_analysis.
"""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from .config import get_settings
from .db import get_client
from .llm import tool_call_multimodal

SYSTEM = """Du bist ein visueller Content-Analyst für Social Media. Du bekommst
ein oder mehrere Bilder eines Instagram-Posts (bei Videos mehrere Frames in
zeitlicher Reihenfolge von Anfang bis Ende). Beschreibe nüchtern und konkret,
WAS visuell passiert — nicht was du vermutest. Achte auf eingeblendeten Text,
Marken/Logos, Personen, Setting und den visuellen Aufhänger der ersten Sekunde.
Antworte auf Deutsch. Nutze IMMER das Tool save_visual."""

TOOL = {
    "name": "save_visual",
    "description": "Speichert die visuelle Analyse eines Posts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "visual_summary": {"type": "string", "description": "Was im Bild/Video passiert (2-4 Sätze)."},
            "scene": {"type": "string", "description": "Setting/Ort (z.B. Rennstrecke, Studio, Outdoor)."},
            "subjects": {"type": "array", "items": {"type": "string"}, "description": "Hauptmotive: Personen, Fahrzeuge, Objekte."},
            "on_screen_text": {"type": "string", "description": "Eingeblendeter Text wörtlich (oder 'keiner')."},
            "branding": {"type": "array", "items": {"type": "string"}, "description": "Sichtbare Marken/Logos/Sponsoren."},
            "visual_hook": {"type": "string", "description": "Was im ersten Frame/Cover zum Stoppen anregt."},
            "mood": {"type": "string", "description": "Farb-/Stimmungseindruck (z.B. dynamisch, edel, roh)."},
            "text_heavy": {"type": "boolean", "description": "Viel Text im Bild?"},
            "people_count": {"type": "integer", "description": "Ungefähre Anzahl sichtbarer Personen."},
        },
        "required": ["visual_summary", "scene", "subjects", "on_screen_text", "branding", "visual_hook", "mood"],
    },
}


def _download(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 16):
                f.write(chunk)


def _resize_jpeg(src: Path, dst: Path, width: int = 768) -> bool:
    res = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-vf", f"scale={width}:-1", "-frames:v", "1",
         "-q:v", "4", str(dst)],
        capture_output=True,
    )
    return dst.exists() and res.returncode == 0


def _duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def _video_frames(video: Path, out_dir: Path, n: int = 4, width: int = 640) -> list[Path]:
    dur = _duration(video) or 12.0
    fracs = [0.05, 0.35, 0.65, 0.9][:n]
    frames = []
    for i, fr in enumerate(fracs):
        t = max(0.0, dur * fr)
        out = out_dir / f"frame_{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", f"scale={width}:-1", "-q:v", "4", str(out)],
            capture_output=True,
        )
        if out.exists():
            frames.append(out)
    return frames


def _image_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def _raw_for(post: dict, db) -> dict | None:
    rows = (
        db.table("raw_payloads").select("payload")
        .eq("entity_type", "post").eq("entity_ref", post["platform_post_id"])
        .order("fetched_at", desc=True).limit(1).execute().data
    )
    return rows[0]["payload"] if rows else None


def _gather_images(post: dict, payload: dict, tmp: Path) -> tuple[list[Path], str]:
    """Liefert eine Liste lokaler JPEGs + die Quelle ('video_frames'|'carousel'|'image')."""
    video_url = (
        payload.get("videoUrl") or post.get("media_url")
        or payload.get("downloadAddr") or payload.get("playAddr")
    )
    if (post.get("is_video") or video_url) and video_url:
        vid = tmp / "v.mp4"
        _download(video_url, vid)
        return _video_frames(vid, tmp), "video_frames"

    # Carousel: childPosts → mehrere displayUrls
    urls: list[str] = []
    for child in (payload.get("childPosts") or [])[:3]:
        u = child.get("displayUrl") if isinstance(child, dict) else None
        if u:
            urls.append(u)
    if not urls:
        u = payload.get("displayUrl") or (payload.get("images") or [None])[0]
        if u:
            urls.append(u)

    out = []
    for i, u in enumerate(urls):
        raw = tmp / f"img_{i}_raw"
        jpg = tmp / f"img_{i}.jpg"
        try:
            _download(u, raw)
            if _resize_jpeg(raw, jpg):
                out.append(jpg)
        except Exception:  # noqa: BLE001 — einzelnes Bild tolerant überspringen
            continue
    source = "carousel" if len(out) > 1 else "image"
    return out, source


def analyze_one(post: dict, db) -> dict | None:
    payload = _raw_for(post, db)
    if not payload:
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        images, source = _gather_images(post, payload, tmp)
        if not images:
            return None
        blocks: list[Any] = [{
            "type": "text",
            "text": (
                f"Instagram-{source}. "
                + ("Frames in zeitlicher Reihenfolge (Anfang→Ende):"
                   if source == "video_frames" else "Bild(er) des Posts:")
            ),
        }]
        blocks += [_image_block(p) for p in images]
        result = tool_call_multimodal(SYSTEM, blocks, TOOL, max_tokens=1200)

    db.table("visual_analysis").upsert(
        {
            "post_id": post["id"],
            "model": get_settings().anthropic_model,
            "source": source,
            "n_images": len(images),
            "payload": result,
        },
        on_conflict="post_id",
    ).execute()
    return {"source": source, "n_images": len(images), "result": result}


def analyze_profile(
    username: str, limit: int | None = None, redo: bool = False, platform: str | None = None
) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    q = db.table("profiles").select("id").eq("username", username)
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    posts = (
        db.table("posts")
        .select("id,platform_post_id,post_type,is_video,caption,media_url")
        .eq("profile_id", prof[0]["id"])
        .execute()
        .data
    )
    if not redo:
        done = {v["post_id"] for v in db.table("visual_analysis").select("post_id").execute().data}
        posts = [p for p in posts if p["id"] not in done]
    if limit:
        posts = posts[:limit]

    print(f"→ {len(posts)} Post(s) visuell zu analysieren.")
    ok = 0
    for i, p in enumerate(posts, 1):
        try:
            res = analyze_one(p, db)
            if res:
                ok += 1
                print(f"  [{i}/{len(posts)}] {p['platform_post_id']} ({res['source']}, "
                      f"{res['n_images']} Bilder): {res['result'].get('scene', '')}")
            else:
                print(f"  [{i}/{len(posts)}] {p['platform_post_id']}: keine Bilder — übersprungen")
        except Exception as e:  # noqa: BLE001 — pro Post tolerant
            print(f"  [{i}/{len(posts)}] {p['platform_post_id']}: FEHLER {e}")
    return {"profile": username, "analyzed": ok, "attempted": len(posts)}
