"""VR01 production readiness gate.

A merged rule is not automatically permitted to send. The existing
operational email/follow-up workers still use SQLite persistence, so this
module intentionally fails closed until they have a MySQL implementation.
"""
from __future__ import annotations

import os

REQUIRED_GRAPH = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EDNNA_EMAIL_FROM")
REQUIRED_MYSQL = ("EDDY_DB_HOST", "EDDY_DB_USER", "EDDY_DB_PASSWORD", "EDDY_DB_NAME")

def verificar_prontidao_vr01(environ=None) -> dict:
    env = os.environ if environ is None else environ
    missing = [k for k in (*REQUIRED_GRAPH, *REQUIRED_MYSQL) if not env.get(k)]
    mysql = str(env.get("EDDY_DB_ENGINE", "")).lower() == "mysql"
    transport = str(env.get("EDDY_VR01_TRANSPORT_MYSQL_READY", "false")).lower() == "true"
    recipient = str(env.get("EDDY_VR01_RECIPIENT_RESOLVER_READY", "false")).lower() == "true"
    reply = str(env.get("EDDY_VR01_REPLY_RECONCILIATION_READY", "false")).lower() == "true"
    audit = str(env.get("EDDY_VR01_REDMINE_MYSQL_AUDIT_READY", "false")).lower() == "true"
    enabled = str(env.get("EDDY_VR01_EXTERNAL_ENABLED", "false")).lower() == "true"
    blockers = []
    if missing:
        blockers.append("CREDENCIAIS_AUSENTES")
    if not mysql:
        blockers.append("PERSISTENCIA_NAO_MYSQL")
    if not transport:
        blockers.append("TRANSPORTE_MYSQL_NAO_HOMOLOGADO")
    if not recipient:
        blockers.append("DESTINATARIOS_NAO_HOMOLOGADOS")
    if not reply:
        blockers.append("RECEPCAO_RESPOSTAS_NAO_HOMOLOGADA")
    if not audit:
        blockers.append("AUDITORIA_REDMINE_NAO_HOMOLOGADA")
    if not enabled:
        blockers.append("EXECUCAO_EXTERNA_DESABILITADA")
    return {"pronto": not blockers, "bloqueios": blockers, "credenciais_ausentes": missing,
            "observacao": "Flags de prontidao exigem homologacao real; nao substituem testes."}
