"""Supabase-Zugriff.

Zwei Wege:
  * `get_client()` — PostgREST-Client (service_role) für normale Lese-/Schreib-Ops.
  * `run_sql()` — Management-API Query-Endpoint, um DDL (Schema) auszuführen.
    Braucht den SUPABASE_ACCESS_TOKEN (Management-Token), kein DB-Passwort.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from supabase import Client, create_client

from .config import get_settings


@lru_cache
def get_client() -> Client:
    """PostgREST/Supabase-Client mit service_role (umgeht RLS)."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


def run_sql(sql: str) -> Any:
    """Führt beliebiges SQL über die Supabase Management-API aus.

    Genutzt für Schema-Migrationen. Erfordert SUPABASE_ACCESS_TOKEN.
    """
    s = get_settings()
    if not s.supabase_access_token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN fehlt — für DDL benötigt.")

    url = f"https://api.supabase.com/v1/projects/{s.supabase_project_ref}/database/query"
    resp = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {s.supabase_access_token}",
            "Content-Type": "application/json",
        },
        json={"query": sql},
        timeout=120.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Management-API SQL fehlgeschlagen ({resp.status_code}): {resp.text}"
        )
    return resp.json()
