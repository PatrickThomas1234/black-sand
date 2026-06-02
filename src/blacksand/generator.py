"""Build #27b — KI-Entwurfs-Generator.

Schließt die Schleife von Analyse zu Erstellung: aus Playbook + Nische-Intelligenz
+ Trend-Radar + Gewinner-Mustern generiert Claude konkrete Post-Konzepte
(Hook, Caption, Format, beste Zeit, Hashtags) zu einem Thema/Ziel. Jedes Konzept
wird zusätzlich mit der datenbasierten ML-Wahrscheinlichkeit P(guter Post) bewertet.
"""

from __future__ import annotations

import json
from typing import Any

from .llm import tool_call

SYSTEM = """Du bist Senior Content-Stratege für Instagram. Du bekommst die
gelernten Erfolgsmuster eines Kanals (Playbook, Nische-Intelligenz, aktuelle
Trends, optimales Posting-Rezept). Generiere zu Thema/Ziel des Nutzers mehrere
konkrete, sofort umsetzbare POST-KONZEPTE, die diese Muster gezielt ausnutzen.
Jedes Konzept: starker Hook, fertige Caption, passendes Format, beste Zeit,
Hashtags. Begründe kurz, welches Muster es ausnutzt. Antworte auf Deutsch.
Nutze IMMER das Tool save_concepts."""

TOOL = {
    "name": "save_concepts",
    "description": "Speichert generierte Post-Konzepte.",
    "input_schema": {
        "type": "object",
        "properties": {
            "concepts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "format": {"type": "string", "description": "z.B. Reel, Carousel, Vergleichsvideo"},
                        "hook": {"type": "string", "description": "Aufhänger der ersten Sekunde/Zeile"},
                        "caption": {"type": "string"},
                        "best_time": {"type": "string", "description": "Wochentag + Tageszeit"},
                        "hashtags": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string", "description": "welches Erfolgsmuster es ausnutzt"},
                    },
                    "required": ["title", "format", "hook", "caption", "rationale"],
                },
            },
        },
        "required": ["concepts"],
    },
}


def _context(username: str, platform: str | None) -> dict:
    ctx: dict[str, Any] = {}
    try:
        from .insights import latest_playbook

        pb = latest_playbook(username, platform)
        if pb:
            p = pb["payload"]
            ctx["best_pattern"] = p.get("best_pattern")
            ctx["recommendations"] = p.get("recommendations", [])[:5]
    except Exception:  # noqa: BLE001
        pass
    try:
        from .niche_intel import latest_niche

        n = latest_niche(username, platform)
        if n:
            p = n["payload"]
            ctx["niche"] = {k: p.get(k) for k in ("winning_formats", "winning_hooks", "topic_patterns", "what_to_adapt")}
    except Exception:  # noqa: BLE001
        pass
    try:
        from .radar import niche_radar

        r = niche_radar(username, platform)
        if r:
            ctx["trends"] = {"hot_hashtags": [h["hashtag"] for h in r.get("hot_hashtags", [])][:10],
                             "hot_formats": [f["format"] for f in r.get("hot_formats", []) if f["trend"] in ("↑", "🆕")]}
    except Exception:  # noqa: BLE001
        pass
    return ctx


def _objectify(items: list) -> list[dict]:
    out = []
    for x in items:
        if isinstance(x, dict):
            out.append(x)
        elif isinstance(x, str) and x.strip():
            try:
                p = json.loads(x)
                out.append(p if isinstance(p, dict) else {"title": x.strip()})
            except (ValueError, TypeError):
                out.append({"title": x.strip()})
    return out


def generate_concepts(username: str, brief: str, n: int = 3,
                      platform: str | None = None) -> list[dict[str, Any]]:
    username = username.strip().lstrip("@")
    ctx = _context(username, platform)
    user = (
        f"KANAL: @{username}\n"
        f"GELERNTE ERFOLGSMUSTER (JSON):\n```json\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n```\n\n"
        f"THEMA/ZIEL DES NUTZERS:\n{brief}\n\n"
        f"Generiere {n} konkrete Post-Konzepte."
    )
    res = tool_call(SYSTEM, user, TOOL, max_tokens=3000)
    concepts = _objectify(res.get("concepts", []))

    # Jedes Konzept datenbasiert bewerten (ML P(guter Post) über das Content-Embedding)
    try:
        from .ml import predict_good

        for c in concepts:
            text = f"{c.get('hook', '')}\n{c.get('caption', '')}"
            pg = predict_good(text)
            if pg:
                c["prob_good"] = pg["prob_good"]
        concepts.sort(key=lambda c: c.get("prob_good", 0), reverse=True)
    except Exception:  # noqa: BLE001
        pass
    return concepts
