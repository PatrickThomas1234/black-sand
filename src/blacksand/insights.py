"""Phase 4 — Content-Playbook.

Synthetisiert aus den datengetriebenen Aggregaten (analytics.feature_aggregates)
+ den Top/Flop-Post-Analysen ein konkretes, umsetzbares Playbook für den Kanal.
Speichert es in profile_insights.
"""

from __future__ import annotations

import json
from typing import Any

from .analytics import feature_aggregates
from .db import get_client
from .llm import tool_call

SYSTEM = """Du bist ein Senior Social-Media-Strategieberater für Instagram.
Du bekommst die VERDICHTETEN PERFORMANCE-DATEN eines Kanals: durchschnittliche
baseline-relative z-Scores (>0 = überdurchschnittlich für DIESEN Kanal) und
Engagement-Raten, aufgeschlüsselt nach Format, Audio-Art, Wochentag, Uhrzeit,
Caption-Länge, Hashtag-Anzahl und Themen — plus die besten und schwächsten Posts
mit KI-Analyse.

Leite daraus ein konkretes, datenbasiertes Playbook ab. Regeln:
- Begründe JEDE Empfehlung mit den konkreten Zahlen aus den Daten (z-Score, n).
- Sei spezifisch und umsetzbar, keine generischen Floskeln.
- Beachte kleine Stichproben (niedriges n) und formuliere dort vorsichtiger.
- Halte das Feld 'evidence' knapp (max. 1 Satz mit den Kernzahlen).
- WICHTIG: Gib Arrays als native JSON-Arrays zurück, niemals als String.
- Antworte auf Deutsch. Nutze IMMER das Tool save_playbook."""

TOOL = {
    "name": "save_playbook",
    "description": "Speichert das datenbasierte Content-Playbook des Kanals.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "2-3 Sätze Kernbefund."},
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Was nachweislich funktioniert (mit Zahlen).",
            },
            "weaknesses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Was nachweislich schwächer läuft (mit Zahlen).",
            },
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string", "description": "z.B. Format, Timing, Hook, Caption, Audio, Thema"},
                        "advice": {"type": "string"},
                        "evidence": {"type": "string", "description": "die Datenbegründung (z-Score, n)"},
                    },
                    "required": ["area", "advice", "evidence"],
                },
            },
            "content_ideas": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "3-5 konkrete nächste Post-Ideen, abgeleitet aus den Mustern. "
                    "Je Eintrag EIN String im Format: "
                    "'Titel — Format — konkreter Hook-Vorschlag — kurze Begründung'."
                ),
            },
            "best_pattern": {
                "type": "object",
                "properties": {
                    "format": {"type": "string"},
                    "weekday": {"type": "string"},
                    "time": {"type": "string"},
                    "caption_style": {"type": "string"},
                    "audio": {"type": "string"},
                },
                "description": "Das optimale Posting-Rezept laut Daten.",
            },
        },
        "required": ["summary", "strengths", "weaknesses", "recommendations", "content_ideas", "best_pattern"],
    },
}


def _as_list(v: Any) -> list:
    """Liste zurückgeben; einen JSON-String einer Liste parsen; sonst einpacken."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else [parsed]
        except (ValueError, TypeError):
            # Kaputtes/abgeschnittenes JSON nicht als ein Riesen-Item einschleusen
            return []
    return []


def _as_obj(v: Any) -> dict | None:
    """Dict zurückgeben; einen JSON-String eines Dicts parsen; sonst None."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            pass
    return None


def _normalize_playbook(pb: dict[str, Any]) -> dict[str, Any]:
    """Gleicht LLM-Output-Varianz aus (z.B. als JSON-String stringifizierte Listen)."""
    for key in ("strengths", "weaknesses", "recommendations", "content_ideas"):
        if key in pb:
            pb[key] = _as_list(pb[key])

    # recommendations & content_ideas sollen Objekte enthalten — reine Strings
    # nicht verwerfen, sondern in ein Minimal-Objekt verpacken (kein Datenverlust).
    def _objectify(items: list, str_key: str) -> list:
        out = []
        for x in items:
            obj = _as_obj(x)
            if obj is not None:
                out.append(obj)
            elif isinstance(x, str) and x.strip():
                out.append({str_key: x.strip()})
        return out

    pb["recommendations"] = _objectify(pb.get("recommendations", []), "advice")
    pb["content_ideas"] = _objectify(pb.get("content_ideas", []), "title")
    if not isinstance(pb.get("best_pattern"), dict):
        pb["best_pattern"] = _as_obj(pb.get("best_pattern")) or {}
    return pb


def build_playbook(username: str, platform: str | None = None) -> dict[str, Any]:
    db = get_client()
    username = username.strip().lstrip("@")
    q = db.table("profiles").select("id").eq("username", username)
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        raise RuntimeError(f"Profil @{username} nicht in der DB.")

    agg = feature_aggregates(username, platform)
    if not agg:
        raise RuntimeError("Keine Daten für Aggregate — erst ingesten/scoren.")

    user = (
        f"KANAL: @{username}\n"
        f"Verdichtete Performance-Daten (JSON):\n```json\n"
        f"{json.dumps(agg, ensure_ascii=False, indent=2)}\n```"
    )
    playbook = _normalize_playbook(tool_call(SYSTEM, user, TOOL, max_tokens=12000))

    from .config import get_settings

    db.table("profile_insights").insert(
        {
            "profile_id": prof[0]["id"],
            "kind": "playbook",
            "payload": playbook,
            "aggregates": agg,
            "model": get_settings().anthropic_model,
        }
    ).execute()
    return {"playbook": playbook, "aggregates": agg}


def latest_playbook(username: str, platform: str | None = None) -> dict | None:
    db = get_client()
    q = db.table("profiles").select("id").eq("username", username.strip().lstrip("@"))
    if platform:
        q = q.eq("platform", platform)
    prof = q.execute().data
    if not prof:
        return None
    rows = (
        db.table("profile_insights")
        .select("payload,aggregates,model,created_at")
        .eq("profile_id", prof[0]["id"])
        .eq("kind", "playbook")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None
