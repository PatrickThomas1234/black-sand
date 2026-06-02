"""Einfaches Passwort-Login fürs Dashboard.

Passwort kommt aus der Umgebung (DASHBOARD_PASSWORD) bzw. den Streamlit-Secrets.
Ist KEIN Passwort gesetzt (lokal), bleibt das Dashboard offen.
"""

from __future__ import annotations

import hmac
import os

import streamlit as st


def _password() -> str:
    pw = os.getenv("DASHBOARD_PASSWORD", "")
    if not pw:
        try:  # auf Streamlit Cloud via st.secrets
            pw = st.secrets.get("DASHBOARD_PASSWORD", "")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pw = ""
    return pw or ""


def require_login() -> None:
    pw = _password()
    if not pw:
        return  # kein Passwort gesetzt → offen (lokale Entwicklung)
    if st.session_state.get("bs_authed"):
        return

    st.markdown("## 🔒 Blacksand")
    st.caption("Bitte einloggen.")
    with st.form("bs_login"):
        entered = st.text_input("Passwort", type="password")
        ok = st.form_submit_button("Anmelden")
    if ok:
        if hmac.compare_digest(entered, pw):
            st.session_state["bs_authed"] = True
            st.rerun()
        else:
            st.error("Falsches Passwort.")
    st.stop()
