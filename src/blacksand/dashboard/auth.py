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


def require_login() -> None:
    users = _users()
    single_pw = _secret("DASHBOARD_PASSWORD")
    if not users and not single_pw:
        return  # kein Login konfiguriert → offen (lokale Entwicklung)
    if st.session_state.get("bs_authed"):
        return

    st.markdown("## 🔒 Blacksand")
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
