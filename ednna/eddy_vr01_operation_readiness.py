"""Operation-specific VR01 readiness, independent of unrelated later stages.

No flag is set here; operators must homologate real integrations separately.
This module never sends email, updates Redmine or mutates MySQL.
"""
from __future__ import annotations

import os

# The global execution kill switch is mandatory for every operation.
# Per-operation gates prevent reply/recipient readiness from blocking Redmine
# assumption, while still requiring all dependencies for each later action.
OPERATION_REQUIREMENTS = {
    "ASSUMIR_REDMINE": ("EDDY_VR01_REDMINE_MYSQL_AUDIT_READY",),
    "BUSCAR_CONTATO_BP": (),
    "SOLICITAR_AUTORIZACAO_PORTAL": (
        "EDDY_VR01_TRANSPORT_MYSQL_READY",
        "EDDY_VR01_RECIPIENT_RESOLVER_READY",
    ),
    # Moving into the waiting phase does not assert that reply processing is homologated.
    # Evidence-based confirmation and follow-up still require the reply gate.
    "MONITORAR_CLIENTE": (),
    "FOLLOWUP_CLIENTE": (
        "EDDY_VR01_TRANSPORT_MYSQL_READY",
        "EDDY_VR01_RECIPIENT_RESOLVER_READY",
        "EDDY_VR01_REPLY_RECONCILIATION_READY",
    ),
    "CONFIRMACAO_VALIDADA": ("EDDY_VR01_REPLY_RECONCILIATION_READY",),
    "REGISTRAR_EVIDENCIAS_REDMINE": (
        "EDDY_VR01_REPLY_RECONCILIATION_READY",
        "EDDY_VR01_REDMINE_MYSQL_AUDIT_READY",
    ),
    "DEVOLVER_AO_RESPONSAVEL_ORIGINAL": (
        "EDDY_VR01_REDMINE_MYSQL_AUDIT_READY",
    ),
    "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA": (
        "EDDY_VR01_TRANSPORT_MYSQL_READY",
        "EDDY_VR01_RECIPIENT_RESOLVER_READY",
    ),
}
MYSQL_CREDENTIALS = ("EDDY_DB_HOST", "EDDY_DB_USER", "EDDY_DB_PASSWORD", "EDDY_DB_NAME")
GRAPH_CREDENTIALS = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EDNNA_EMAIL_FROM")
GRAPH_OPERATIONS = frozenset((
    "SOLICITAR_AUTORIZACAO_PORTAL", "NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA",
    "FOLLOWUP_CLIENTE",
))


def verificar_prontidao_operacao_vr01(operation: str, environ=None) -> dict:
    env = os.environ if environ is None else environ
    if operation not in OPERATION_REQUIREMENTS:
        return {"operacao": operation, "pronto": False,
                "bloqueios": ["OPERACAO_DESCONHECIDA"], "credenciais_ausentes": []}
    blockers = []
    missing = [name for name in MYSQL_CREDENTIALS if not env.get(name)]
    if operation in GRAPH_OPERATIONS:
        missing.extend(name for name in GRAPH_CREDENTIALS if not env.get(name))
    if missing:
        blockers.append("CREDENCIAIS_AUSENTES")
    if str(env.get("EDDY_DB_ENGINE", "")).lower() != "mysql":
        blockers.append("PERSISTENCIA_NAO_MYSQL")
    if str(env.get("EDDY_VR01_EXTERNAL_ENABLED", "false")).lower() != "true":
        blockers.append("EXECUCAO_EXTERNA_DESABILITADA")
    for flag in OPERATION_REQUIREMENTS[operation]:
        if str(env.get(flag, "false")).lower() != "true":
            blockers.append({
                "EDDY_VR01_TRANSPORT_MYSQL_READY": "TRANSPORTE_MYSQL_NAO_HOMOLOGADO",
                "EDDY_VR01_RECIPIENT_RESOLVER_READY": "DESTINATARIOS_NAO_HOMOLOGADOS",
                "EDDY_VR01_REPLY_RECONCILIATION_READY": "RECEPCAO_RESPOSTAS_NAO_HOMOLOGADA",
                "EDDY_VR01_REDMINE_MYSQL_AUDIT_READY": "AUDITORIA_REDMINE_NAO_HOMOLOGADA",
            }[flag])
    return {"operacao": operation, "pronto": not blockers,
            "bloqueios": blockers, "credenciais_ausentes": missing,
            "observacao": "Flags exigem homologacao real; aprovacao por operacao e preflight continuam obrigatorios."}
