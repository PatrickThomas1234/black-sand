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
baseline-relativen z-Score) sowie konkrete BEISPIEL-POSTS (Top & Flop des Kanals
mit Hook/Format/visuellem Aufhänger und Begründung), die Erkenntnisse der NISCHE
und die stärksten Posts vergleichbarer KONKURRENTEN.

Du bekommst einen ENTWURF für einen neuen Post. Gehe so vor:
1. Ordne den Entwurf den ähnlichsten Beispiel-Posts zu (Kanal + Nische + Konkurrenz).
2. Prognostiziere das Rating relativ zum Kanal und begründe es mit konkreten
   Beispielen und Zahlen (nicht nur abstrakt).
3. Sei ehrlich über Unsicherheit (kleine Datenbasis = niedrigere Konfidenz).
4. Gib konkrete, umsetzbare Verbesserungen — orientiert an dem, was bei Top-Posts
   und bei den Konkurrenten nachweislich funktioniert.
Antworte auf Deutsch. Nutze IMMER das Tool save_forecast."""

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


def _post_brief(r: Any) -> dict:
    """Kompakte Feature-Zusammenfassung eines Posts (für Beispiel-Kontext)."""
    import pandas as pd

    a = r["analysis"] if isinstance(r.get("analysis"), dict) else {}
    v = r["visual"] if isinstance(r.get("visual"), dict) else {}
    score = r.get("zscore")
    return {
        "score": round(float(score), 2) if pd.notna(score) else None,
        "rating": r.get("rating"),
        "post_type": r.get("post_type"),
        "er": r.get("engagement_rate"),
        "hook": a.get("hook"),
        "format": a.get("content_format"),
        "drivers": (a.get("performance_drivers") or [])[:3],
        "visual_hook": v.get("visual_hook"),
        "caption": (r.get("caption") or "")[:120],
    }


def _rich_context(username: str, platform: str | None) -> dict:
    """Beispiel-Posts (Kanal Top/Flop), Nische-Intelligenz und Konkurrenz-Top-Posts.

    Komplett defensiv: jede Quelle einzeln in try/except, damit der Forecast auch
    läuft, wenn eine Teilkomponente (noch) keine Daten hat.
    """
    ctx: dict[str, Any] = {}
    try:
        from .analytics import profile_dataframe

        df = profile_dataframe(username, platform)
        df = df.dropna(subset=["zscore"]) if not df.empty else df
        if not df.empty:
            ctx["channel_top_posts"] = [_post_brief(r) for _, r in df.sort_values("zscore", ascending=False).head(5).iterrows()]
            ctx["channel_flop_posts"] = [_post_brief(r) for _, r in df.sort_values("zscore").head(5).iterrows()]
    except Exception:  # noqa: BLE001
        pass
    try:
        from .niche_intel import latest_niche

        n = latest_niche(username, platform)
        if n:
            p = n["payload"]
            ctx["niche"] = {k: p.get(k) for k in ("winning_formats", "winning_hooks", "best_timing", "topic_patterns", "what_to_adapt")}
    except Exception:  # noqa: BLE001
        pass
    try:
        from .analytics import profile_dataframe
        from .niche_intel import niche_usernames

        _, comps = niche_usernames(username, platform)
        rows = []
        for u in comps[:5]:
            d = profile_dataframe(u)
            d = d.dropna(subset=["engagement_rate"]) if not d.empty else d
            for _, r in d.sort_values("engagement_rate", ascending=False).head(2).iterrows():
                rows.append({"account": u, "er": r.get("engagement_rate"),
                             "post_type": r.get("post_type"), "caption": (r.get("caption") or "")[:120]})
        if rows:
            ctx["competitor_top_posts"] = rows
    except Exception:  # noqa: BLE001
        pass
    return ctx


def forecast_post(
    username: str, draft: str, post_type: str | None = None, platform: str | None = None
) -> dict[str, Any]:
    username = username.strip().lstrip("@")
    agg = feature_aggregates(username, platform)
    if not agg:
        raise RuntimeError("Keine Kanal-Daten für die Prognose vorhanden.")
    pb = latest_playbook(username, platform)

    context = {"aggregates": agg}
    if pb:
        context["playbook"] = pb["payload"]
    context.update(_rich_context(username, platform))

    # Semantische Nachbarn: die ähnlichsten vergangenen Posts (Kanal+Nische+Konkurrenz)
    try:
        from .embeddings import similar_to_text

        sims = similar_to_text(draft, k=8)
        if sims:
            context["semantically_similar_posts"] = sims
    except Exception:  # noqa: BLE001 — Embeddings optional
        pass

    # ML-Modell: kalibrierte Wahrscheinlichkeit für "guter Post" (nur wenn brauchbar)
    try:
        from .ml import predict_good

        ml = predict_good(draft)
        if ml and (ml.get("cv_auc") or 0) >= 0.58:
            context["ml_good_probability"] = ml
    except Exception:  # noqa: BLE001 — Modell optional
        pass

    user = (
        f"KANAL: @{username}\n"
        f"GELERNTE MUSTER + BEISPIELE (JSON):\n```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```\n\n"
        f"ENTWURF FÜR NEUEN POST:\n"
        f"- Geplantes Format: {post_type or '(nicht angegeben)'}\n"
        f"- Idee/Caption/Skript:\n{draft}"
    )
    return tool_call(SYSTEM, user, TOOL, max_tokens=2500)
