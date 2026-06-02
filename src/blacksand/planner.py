"""Build #27c — Content-Kalender / Posting-Planer.

Erzeugt einen mehrwöchigen Posting-Plan, der die besten Tage/Zeiten des Kanals
(Playbook best_pattern) mit erfolgreichen Formaten/Themen und aktuellen Nische-
Trends kombiniert. Schließt die Schleife: aus Erkenntnissen wird ein konkreter
Fahrplan, was wann zu posten ist.
"""

from __future__ import annotations

import json
from typing import Any

from .generator import _context, _objectify
from .llm import tool_call

SYSTEM = """Du bist Content-Planer für Instagram. Du bekommst die Erfolgsmuster
eines Kanals (bestes Posting-Rezept, Nische-Intelligenz, aktuelle Trends). Erzeuge
einen konkreten Posting-Plan: pro Slot Tag+Zeit (gemäß bestem Timing), Format,
Thema, ein fertiger Hook und eine kurze Begründung. Variiere Formate/Themen sinnvoll,
nutze aufsteigende Trends. Antworte auf Deutsch. Nutze IMMER das Tool save_plan."""

TOOL = {
    "name": "save_plan",
    "description": "Speichert den Posting-Plan.",
    "input_schema": {
        "type": "object",
        "properties": {
            "plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slot": {"type": "string", "description": "z.B. 'Woche 1 · Sa 18–22 Uhr'"},
                        "format": {"type": "string"},
                        "topic": {"type": "string"},
                        "hook": {"type": "string"},
                        "rationale": {"type": "string"},
                    },
                    "required": ["slot", "format", "topic", "hook"],
                },
            },
        },
        "required": ["plan"],
    },
}


def build_calendar(username: str, weeks: int = 2, per_week: int = 3,
                   platform: str | None = None) -> list[dict[str, Any]]:
    username = username.strip().lstrip("@")
    ctx = _context(username, platform)
    user = (
        f"KANAL: @{username}\n"
        f"ERFOLGSMUSTER (JSON):\n```json\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Erzeuge einen {weeks}-Wochen-Posting-Plan mit ca. {per_week} Posts pro Woche. "
        f"Nutze die besten Tage/Zeiten, variiere Formate/Themen und baue aktuelle Trends ein."
    )
    res = tool_call(SYSTEM, user, TOOL, max_tokens=3000)
    return _objectify(res.get("plan", []))
