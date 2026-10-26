"""VR01 pilot: prepare a human validation request, never send without approval.

Internal validation is independent of the external-acquirer readiness flags.
This module intentionally has no Graph/Redmine write side effects.
"""
from __future__ import annotations

import re

PILOT_ISSUE = 49227
VALIDATION_ACTION = "COBRAR_VALIDACAO_RECEPCAO"
EMAIL = re.compile(r"^[^\\s@]+@netunna\\.com\\.br$", re.I)
SUBJECT = "Validação de movimentos VR Benefícios - REDE SANDER - #49227"
BODY = """Olá!

A VR Benefícios confirmou que os CNPJs credenciados sob a matriz
91.411.256/0001-47 entram automaticamente no arquivo VR_NETUNNA_SANDER.

Por gentileza, valide se há movimentos das filiais:
- 85: 91.411.256/0057-00
- 86: 91.411.256/0060-05
- 87: 91.411.256/0059-63

Informe se os registros foram recebidos. Se houver vendas ausentes,
encaminhe exemplos com CNPJ, data da venda e valor bruto.

Chamado Redmine: #49227.
EDDY - Operações EDI Netunna
"""


def preparar_validacao_interna(issue: dict, decision: dict, *, approved_email: str = "") -> dict:
    """Fail closed if issue/decision/recipient have not been explicitly verified."""
    if int(issue.get("id") or 0) != PILOT_ISSUE:
        return {"estado": "BLOQUEADO_FORA_PILOTO"}
    status = issue.get("status") or {}
    if status.get("is_closed") or any(x in str(status.get("name") or "").casefold()
                                     for x in ("conclu", "fechado", "cancelad", "rejeitad")):
        return {"estado": "BLOQUEADO_CHAMADO_TERMINAL"}
    if (decision.get("acao") != VALIDATION_ACTION
            or decision.get("destino") != "RESPONSAVEL_REDMINE"):
        return {"estado": "BLOQUEADO_DECISAO"}
    if not issue.get("updated_on"):
        return {"estado": "BLOQUEADO_VERSAO"}
    # Approval must be a verified institutional address, never guessed from name.
    if not EMAIL.fullmatch(approved_email.strip()):
        return {"estado": "AGUARDA_DESTINATARIO_HOMOLOGADO"}
    return {"estado": "PRONTO_PARA_APROVACAO_ENVIO_INTERNO",
            "chamado_id": PILOT_ISSUE, "redmine_updated_on": issue["updated_on"],
            "destinatario": approved_email.strip().lower(),
            "assunto": SUBJECT, "corpo": BODY,
            "envios_realizados": 0, "redmine_escritas": 0}


def aprovar_acao_interna(action: dict, issue: dict, *, approved_email: str = "") -> dict:
    """Generate the exact versioned approval payload consumed by VR01 dispatcher.

    This does not grant send permission: dispatcher still checks MySQL claim,
    live Redmine preflight, Sent Items and readiness flags.
    """
    if int(action.get("chamado_id") or 0) != PILOT_ISSUE:
        return {"estado": "BLOQUEADO_FORA_PILOTO"}
    if action.get("acao") != VALIDATION_ACTION or action.get("destino") != "RESPONSAVEL_REDMINE":
        return {"estado": "BLOQUEADO_ACAO"}
    if not action.get("action_key") or action.get("redmine_updated_on") != issue.get("updated_on"):
        return {"estado": "BLOQUEADO_VERSAO"}
    prepared = preparar_validacao_interna(issue, action, approved_email=approved_email)
    if prepared["estado"] != "PRONTO_PARA_APROVACAO_ENVIO_INTERNO":
        return prepared
    return {"estado": "APROVACAO_PREPARADA", "action_key": action["action_key"],
            "approval": {"redmine_updated_on": action["redmine_updated_on"],
                         "acao": VALIDATION_ACTION,
                         "to": prepared["destinatario"], "cc": [],
                         "subject": prepared["assunto"], "body": prepared["corpo"]},
            "envios_realizados": 0}
