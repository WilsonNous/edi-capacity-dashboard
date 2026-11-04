"""Shared read policy: observation uses persisted state, external actions preflight live.

This is a safe first stage toward coordinated collection across all EDDY rules.
No remote calls or external effects are performed here.
"""
from __future__ import annotations


def observational_state(chamado_id: int, row: dict | None) -> dict:
    """Report persisted lifecycle without issuing a Redmine request.

    A missing lifecycle is not initialized implicitly. A cached snapshot is
    never authorization for a Redmine write or an email.
    """
    if row is None:
        return {"chamado_id": int(chamado_id),
                "estado": "AGUARDA_INICIALIZACAO_MYSQL",
                "externo": False, "fonte": "MYSQL_LOCAL"}
    fase = row.get("fase")
    return {"chamado_id": int(chamado_id),
            **({"acao": "CONCLUIDO"} if fase == "NOTIFICACAO_INTERNA_CONFIRMADA" and bool(row.get("notificado")) else {}),
            "fase": fase,
            "estado": "OBSERVACAO_LOCAL",
            "operacao_pendente": row.get("operacao_pendente"),
            "externo": False, "fonte": "MYSQL_LOCAL"}
