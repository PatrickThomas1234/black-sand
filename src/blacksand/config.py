"""Zentrale Konfiguration — lädt Secrets aus der .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

# override=True: Werte aus der .env haben Vorrang vor bereits gesetzten
# Umgebungsvariablen (manche Umgebungen injizieren z.B. ein leeres
# ANTHROPIC_API_KEY in den Subprozess, das sonst die .env überschatten würde).
load_dotenv(override=True)


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Umgebungsvariable {name} fehlt. Trage sie in die .env ein "
            f"(Vorlage: .env.example)."
        )
    return value


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_project_ref: str
    supabase_access_token: str
    supabase_service_role_key: str
    supabase_anon_key: str
    apify_token: str
    apify_instagram_actor: str
    whisper_model: str
    anthropic_api_key: str
    anthropic_model: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        supabase_url=_require("SUPABASE_URL"),
        supabase_project_ref=_require("SUPABASE_PROJECT_REF"),
        supabase_access_token=os.getenv("SUPABASE_ACCESS_TOKEN", ""),
        supabase_service_role_key=_require("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        apify_token=os.getenv("APIFY_TOKEN", ""),
        apify_instagram_actor=os.getenv(
            "APIFY_INSTAGRAM_ACTOR", "apify/instagram-scraper"
        ),
        whisper_model=os.getenv("WHISPER_MODEL", "small"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"),
    )
