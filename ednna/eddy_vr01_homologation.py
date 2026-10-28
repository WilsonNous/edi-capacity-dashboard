"""VR01 pilot #50318 homologation evidence gate; no external actions.

Explicit evidence is required for each prerequisite. This is a review artifact,
not an authorization to dispatch or modify Redmine.
"""
from __future__ import annotations

PILOT = 50318
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


def homologar_observacao_vr01(evidencias: dict, *, autorizacao_explicita: bool = False) -> dict:
    """Approve the pilot's observational rule, never its external execution.

    Operator acceptance may authorize an observable pilot before all external
    integrations are validated. It does not assert that missing evidence exists.
    """
    avaliacao = avaliar_homologacao_vr01(evidencias)
    if avaliacao["estado"] == "BLOQUEADO_ESCOPO" or autorizacao_explicita is not True:
        return {**avaliacao, "estado": "HOMOLOGACAO_OBSERVACIONAL_BLOQUEADA",
                "modo": "SOMENTE_LEITURA", "envios_autorizados": False,
                "redmine_escritas_autorizadas": False}
    return {
        **avaliacao,
        "estado": "HOMOLOGADA_SOMENTE_OBSERVACAO",
        "homologada": True,
        "escopo_homologado": "REGRA_VR01_PILOTO_OBSERVACIONAL",
        "modo": "SOMENTE_LEITURA",
        "envios_autorizados": False,
        "redmine_escritas_autorizadas": False,
        "pendencias_execucao_externa": avaliacao["pendencias"],
        "observacao": "Aceite explicito limitado ao piloto observacional; prontidao externa continua independente.",
    }
