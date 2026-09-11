"""Login fürs Dashboard — Benutzername + Passwort (mehrere Nutzer).

Nutzer kommen aus:
  1. Streamlit-Secrets, Tabelle [users]:  benutzername = "passwort"
  2. Env-Variable DASHBOARD_USERS als JSON: {"name": "passwort", ...}

Rückwärtskompatibel: ist KEINE Nutzerliste gesetzt, aber ein einzelnes
DASHBOARD_PASSWORD, gilt der frühere Nur-Passwort-Modus. Ist gar nichts gesetzt
(lokal), bleibt das Dashboard offen.
"""

from __future__ import annotations

import hmac
import json
import os

import streamlit as st


def _secret(key: str, default: str = "") -> str:
    v = os.getenv(key, "")
    if not v:
        try:
            v = st.secrets.get(key, default)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            v = default
    return v or default


def _users() -> dict[str, str]:
    # 1) Streamlit-Secrets [users]-Tabelle
    try:
        tbl = st.secrets.get("users", None)  # type: ignore[attr-defined]
        if tbl:
            return {str(k): str(v) for k, v in dict(tbl).items()}
    except Exception:  # noqa: BLE001
        pass
    # 2) Env DASHBOARD_USERS als JSON
    raw = os.getenv("DASHBOARD_USERS", "")
    if raw:
        try:
            return {str(k): str(v) for k, v in json.loads(raw).items()}
        except (ValueError, TypeError):
            pass
    return {}


def _user_profiles() -> dict[str, list[str]]:
    """Zuordnung Benutzer → erlaubte Profil-Usernames.

    Quellen (wie bei den Nutzern):
      1. Streamlit-Secrets, Tabelle [user_profiles]: benutzer = "user1, user2"
         (oder als TOML-Array: benutzer = ["user1", "user2"])
      2. Env DASHBOARD_USER_PROFILES als JSON: {"benutzer": ["user1", ...]}
    """
    raw_map = None
    # 1) Streamlit-Secrets [user_profiles]
    try:
        tbl = st.secrets.get("user_profiles", None)  # type: ignore[attr-defined]
        if tbl:
            raw_map = dict(tbl)
    except Exception:  # noqa: BLE001
        pass
    # 2) Env DASHBOARD_USER_PROFILES als JSON
    if raw_map is None:
        raw = os.getenv("DASHBOARD_USER_PROFILES", "")
        if raw:
            try:
                raw_map = json.loads(raw)
            except (ValueError, TypeError):
                raw_map = None
    if not raw_map:
        return {}

    out: dict[str, list[str]] = {}
    for k, v in raw_map.items():
        if isinstance(v, str):
            names = [s.strip() for s in v.split(",") if s.strip()]
        elif isinstance(v, (list, tuple)):
            names = [str(s).strip() for s in v if str(s).strip()]
        else:
            names = []
        out[str(k)] = names
    return out


def visible_usernames(user: str | None) -> set[str] | None:
    """Profil-Usernames, die dieser Nutzer sehen darf.

    Rückgabe ``None`` = keine Einschränkung (Admin/sieht alles). Ist der Nutzer
    in der Zuordnung eingetragen, sieht er ausschließlich die dort gelisteten
    Profile (plattformübergreifend nach Username gefiltert).
    """
    if not user:
        return None
    mapping = _user_profiles()
    if user in mapping:
        return set(mapping[user])
    return None


def require_login() -> None:
    users = _users()
    single_pw = _secret("DASHBOARD_PASSWORD")
    if not users and not single_pw:
        return  # kein Login konfiguriert → offen (lokale Entwicklung)
    if st.session_state.get("bs_authed"):
        return

    st.markdown("## 🔒 Social Analyse")
    st.caption("Bitte einloggen.")
    with st.form("bs_login"):
        username = st.text_input("Benutzername") if users else None
        entered = st.text_input("Passwort", type="password")
        ok = st.form_submit_button("Anmelden")
    if ok:
        if users:
            expected = users.get((username or "").strip())
            valid = expected is not None and hmac.compare_digest(entered, expected)
        else:
            valid = hmac.compare_digest(entered, single_pw)
        if valid:
            st.session_state["bs_authed"] = True
            st.session_state["bs_user"] = (username or "").strip() or "admin"
            st.rerun()
        else:
            st.error("Falsche Zugangsdaten.")
    st.stop()
