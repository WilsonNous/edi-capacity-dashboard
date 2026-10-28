"""VR01 pilot #49227 homologation evidence gate; no external actions.

Explicit evidence is required for each prerequisite. This is a review artifact,
not an authorization to dispatch or modify Redmine.
"""
from __future__ import annotations

PILOT = 49227
REQUIRED = (
    "redmine_snapshot_fresco",
    "mysql_snapshot_journals_conciliados",
    "responsavel_original_persistido",
    "assuncao_confirmada_redmine",
    "retorno_confirmado_redmine",
    "transport_mysql_testado_sem_envio",
    "destinatario_validado",
    "respostas_reconciliadas",
    "auditoria_mysql_validada",
)


def avaliar_homologacao_vr01(evidencias: dict) -> dict:
    if not isinstance(evidencias, dict) or type(evidencias.get("chamado_id")) is not int or evidencias["chamado_id"] != PILOT:
        return {"estado": "BLOQUEADO_ESCOPO", "homologada": False, "chamado_id": PILOT, "pendencias": list(REQUIRED)}
    pendencias = [
        name for name in REQUIRED
        if not isinstance(evidencias.get(name), dict)
        or evidencias[name].get("confirmado") is not True
        or not isinstance(evidencias[name].get("referencia"), str)
        or not evidencias[name]["referencia"].strip()
    ]
    return {
        "estado": "EVIDENCIAS_COMPLETAS_PARA_REVISAO" if not pendencias else "HOMOLOGACAO_PENDENTE",
        "homologada": False,
        "chamado_id": PILOT,
        "pendencias": pendencias,
        "observacao": "Checklist completo nao homologa automaticamente nem habilita efeitos externos.",
    }
