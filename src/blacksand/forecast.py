"""Phase 4 — Performance-Prognose für einen Post-Entwurf.

Gegeben eine Idee/Entwurf (Freitext, optional Format), schätzt Claude — auf Basis
der gelernten Kanal-Muster (Aggregate + Playbook) — das wahrscheinliche Rating,
eine Engagement-Spanne und gibt konkrete Verbesserungen + einen optimierten Hook
und Caption-Vorschlag zurück.

Hinweis: Das ist eine LLM-gestützte Heuristik auf Basis der bisherigen Posts,
keine statistische Punktprognose. Mit mehr Daten lässt sich das später durch ein
echtes ML-Modell ergänzen.
"""

from __future__ import annotations

import json
from typing import Any

from .analytics import feature_aggregates
from .insights import latest_playbook
from .llm import tool_call

SYSTEM = """Du bist ein Instagram-Performance-Prognose-Modell. Du kennst die
gelernten Muster eines konkreten Kanals (welche Formate, Hooks, Themen, Audio,
Zeiten, Caption-Längen über- bzw. unterdurchschnittlich performen — gemessen am
baseline-relativen z-Score dieses Kanals).

Du bekommst einen ENTWURF für einen neuen Post. Prognostiziere, wie er relativ
zum Kanal abschneiden wird, und begründe es mit den gelernten Mustern. Sei ehrlich
über Unsicherheit. Gib konkrete, umsetzbare Verbesserungen. Antworte auf Deutsch.
Nutze IMMER das Tool save_forecast."""

TOOL = {
    "name": "save_forecast",
    "description": "Speichert die Performance-Prognose für einen Post-Entwurf.",
    "input_schema": {
        "type": "object",
        "properties": {
            "predicted_rating": {
                "type": "string",
                "enum": ["flop", "below", "avg", "good", "viral"],
                "description": "Erwartetes Rating relativ zum Kanal.",
            },
            "predicted_er_range": {
                "type": "string",
                "description": "Geschätzte Engagement-Rate-Spanne in %, z.B. '3-5%'.",
            },
            "confidence": {
                "type": "string",
                "enum": ["niedrig", "mittel", "hoch"],
                "description": "Wie sicher die Prognose ist (kleine Datenbasis = niedriger).",
            },
            "reasoning": {
                "type": "string",
                "description": "Begründung anhand der konkreten Kanal-Muster (z-Scores).",
            },
            "improvements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Konkrete Stellschrauben, um die Performance zu erhöhen.",
            },
            "optimized_hook": {"type": "string", "description": "Verbesserter Hook-Vorschlag."},
            "optimized_caption": {"type": "string", "description": "Optimierter Caption-Vorschlag."},
            "best_time": {"type": "string", "description": "Empfohlener Posting-Zeitpunkt (Wochentag + Tageszeit) laut Mustern."},
        },
        "required": ["predicted_rating", "predicted_er_range", "confidence", "reasoning", "improvements", "optimized_hook", "best_time"],
    },
}


def forecast_post(username: str, draft: str, post_type: str | None = None) -> dict[str, Any]:
    username = username.strip().lstrip("@")
    agg = feature_aggregates(username)
    if not agg:
        raise RuntimeError("Keine Kanal-Daten für die Prognose vorhanden.")
    pb = latest_playbook(username)

    context = {"aggregates": agg}
    if pb:
        context["playbook"] = pb["payload"]

    user = (
        f"KANAL: @{username}\n"
        f"GELERNTE MUSTER (JSON):\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```\n\n"
        f"ENTWURF FÜR NEUEN POST:\n"
        f"- Geplantes Format: {post_type or '(nicht angegeben)'}\n"
        f"- Idee/Caption/Skript:\n{draft}"
    )
    return tool_call(SYSTEM, user, TOOL, max_tokens=2000)
