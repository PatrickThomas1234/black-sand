"""Gemeinsamer Anthropic-Client für alle LLM-Module."""

from __future__ import annotations

from functools import lru_cache

from .config import get_settings


@lru_cache
def get_anthropic():
    from anthropic import Anthropic

    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY fehlt in der .env — für LLM-Module benötigt."
        )
    return Anthropic(api_key=s.anthropic_api_key)


def tool_call(system: str, user: str, tool: dict, max_tokens: int = 2000) -> dict:
    """Ein erzwungener Tool-Use-Call; gibt das Tool-Input-Dict zurück.

    System-Prompt wird gecacht (spart Tokens bei wiederholten Calls).
    """
    s = get_settings()
    resp = get_anthropic().messages.create(
        model=s.anthropic_model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(
            "Antwort am Token-Limit abgeschnitten — max_tokens erhöhen "
            "(unvollständige Ausgabe wird nicht gespeichert)."
        )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Kein tool_use im Claude-Response.")
