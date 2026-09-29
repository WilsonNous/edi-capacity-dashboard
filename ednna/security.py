"""Autenticação/autorização da EDNNA sobre Azure App Service Easy Auth.

O Easy Auth autentica antes do Streamlit. Este módulo transforma os headers
X-MS-* em perfis locais e aplica RBAC server-side às páginas.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
AUDIT_DB = DATA / "ednna_security.db"

ROLE_ADMIN = "ADMIN"
ROLE_EDI = "EDI"
ROLE_VIEWER = "VIEWER"
ROLE_BLOCKED = "BLOCKED"


def _csv_env(name: str) -> set[str]:
    raw = os.getenv(name, "")
    return {x.strip().lower() for x in raw.replace(";", ",").split(",") if x.strip()}


def _headers() -> dict[str, str]:
    try:
        return {str(k).lower(): str(v) for k, v in st.context.headers.items()}
    except Exception:
        return {}


def _decode_principal(raw: str) -> dict:
    if not raw:
        return {}
    try:
        pad = "=" * (-len(raw) % 4)
        return json.loads(base64.b64decode(raw + pad).decode("utf-8"))
    except Exception:
        return {}


def _claim(principal: dict, *types: str) -> str:
    wanted = {x.lower() for x in types}
    for item in principal.get("claims", []) or []:
        typ = str(item.get("typ") or "").lower()
        if typ in wanted:
            return str(item.get("val") or "").strip()
    return ""


def _groups(principal: dict) -> set[str]:
    vals: set[str] = set()
    for item in principal.get("claims", []) or []:
        typ = str(item.get("typ") or "").lower()
        if typ in {"groups", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"}:
            vals.add(str(item.get("val") or "").strip().lower())
    return {x for x in vals if x}


def _is_azure() -> bool:
    return bool(os.getenv("WEBSITE_INSTANCE_ID") or os.getenv("WEBSITE_SITE_NAME"))


@dataclass(frozen=True)
class UserContext:
    authenticated: bool
    email: str
    name: str
    role: str
    groups: frozenset[str]
    source: str = "easy_auth"

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_edi(self) -> bool:
        return self.role in {ROLE_ADMIN, ROLE_EDI}

    @property
    def is_viewer(self) -> bool:
        return self.role == ROLE_VIEWER


def current_user() -> UserContext:
    h = _headers()
    principal = _decode_principal(h.get("x-ms-client-principal", ""))
    email = (h.get("x-ms-client-principal-name") or _claim(
        principal,
        "preferred_username", "email", "emails",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
    )).strip().lower()
    name = (_claim(principal, "name", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name") or email).strip()
    groups = _groups(principal)

    # Bypass exclusivamente local. No Azure ele é deliberadamente ignorado.
    if not email and not _is_azure() and os.getenv("EDNNA_DEV_BYPASS_AUTH", "").lower() in {"1", "true", "yes", "sim"}:
        email = os.getenv("EDNNA_DEV_USER", "dev@localhost").strip().lower()
        name = os.getenv("EDNNA_DEV_NAME", "Desenvolvimento local").strip()
        role = os.getenv("EDNNA_DEV_ROLE", ROLE_ADMIN).strip().upper()
        if role not in {ROLE_ADMIN, ROLE_EDI, ROLE_VIEWER}:
            role = ROLE_ADMIN
        return UserContext(True, email, name, role, frozenset(), "dev_bypass")

    if not email:
        return UserContext(False, "", "", ROLE_BLOCKED, frozenset(groups))

    allowed_domains = _csv_env("EDNNA_ALLOWED_EMAIL_DOMAINS") or {"netunna.com.br"}
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain not in allowed_domains:
        return UserContext(True, email, name or email, ROLE_BLOCKED, frozenset(groups))

    admins = _csv_env("EDNNA_ADMIN_EMAILS")
    edi = _csv_env("EDNNA_EDI_EMAILS")
    admin_groups = _csv_env("EDNNA_ADMIN_GROUP_IDS")
    edi_groups = _csv_env("EDNNA_EDI_GROUP_IDS")

    if email in admins or bool(groups & admin_groups):
        role = ROLE_ADMIN
    elif email in edi or bool(groups & edi_groups):
        role = ROLE_EDI
    else:
        # Easy Auth já restringe ao tenant corporativo. Usuário autenticado do
        # tenant que não está em listas privilegiadas recebe somente leitura.
        role = ROLE_VIEWER
    return UserContext(True, email, name or email, role, frozenset(groups))


def audit(event: str, detail: str = "", user: UserContext | None = None) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        u = user or current_user()
        with sqlite3.connect(AUDIT_DB) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS security_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                email TEXT,
                role TEXT,
                event TEXT NOT NULL,
                detail TEXT
            )""")
            con.execute(
                "INSERT INTO security_audit(created_at,email,role,event,detail) VALUES(?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), u.email, u.role, event, detail[:2000]),
            )
    except Exception:
        pass


def require_roles(*roles: str) -> UserContext:
    user = current_user()
    allowed = {r.upper() for r in roles}
    if not user.authenticated:
        audit("ACCESS_BLOCKED", "Identidade Easy Auth ausente", user)
        st.error("Acesso não autenticado. Entre novamente com sua conta corporativa Netunna.")
        st.stop()
    if user.role not in allowed:
        audit("ACCESS_DENIED", f"Perfis permitidos: {','.join(sorted(allowed))}", user)
        st.warning("Esta área é restrita ao seu perfil. Você pode consultar o painel geral da EDNNA.")
        if st.button("← Voltar ao painel geral", key="security_back_home"):
            st.switch_page("app.py")
        st.stop()
    return user


def require_admin() -> UserContext:
    return require_roles(ROLE_ADMIN)


def require_edi() -> UserContext:
    return require_roles(ROLE_ADMIN, ROLE_EDI)


def display_name(user: UserContext) -> str:
    from ednna.linguagem import primeiro_nome_por_email
    return primeiro_nome_por_email(user.email, user.name)


def role_label(role: str) -> str:
    return {ROLE_ADMIN: "Administrador EDNNA", ROLE_EDI: "Equipe EDI", ROLE_VIEWER: "Visualizador"}.get(role, role)
