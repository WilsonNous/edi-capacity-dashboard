"""Motor de abertura de relacionamento do EDDY.

Primeira fase: planejamento seguro e auditável. Nenhuma ação externa é
executada por este módulo; o executor precisa ser homologado separadamente.
"""
from __future__ import annotations

from ednna.aprendizado_operacional import obter_autorizacao_motor
from ednna.homologacao import estado_regra, listar_homologacoes_mais_recentes
from ednna.workflows_inclusao import obter_workflow


def avaliar_abertura(regra_id: str, *, dados: dict | None = None) -> dict:
    """Resolve homologação, autorização e checkpoints sem confundir inclusão."""
    rid = str(regra_id or "").strip()
    dados = dict(dados or {})
    if not rid.startswith("ABERTURA-"):
        return {"regra_id": rid, "estado": "OPERACAO_INCOMPATIVEL", "executavel": False}
    homologacao = estado_regra(rid) or {}
    if homologacao.get("estado") not in {"ATIVA", "EM_OBSERVACAO"}:
        return {"regra_id": rid, "estado": "NAO_HOMOLOGADA_OU_SUSPENSA", "executavel": False}
    autorizacao = obter_autorizacao_motor(rid) or {}
    modo = str(autorizacao.get("modo") or "BLOQUEADA").upper()
    player = str(homologacao.get("player") or "").strip().upper()
    workflow = obter_workflow(player)
    if modo not in {"ASSISTIDA", "AUTOMATICA"}:
        estado = "AGUARDANDO_AUTORIZACAO"
    elif workflow.get("prontidao") != "ASSISTIDA_DISPONIVEL":
        estado = "AGUARDANDO_EXECUTOR"
    else:
        # Abertura exige validação própria do procedimento e do canal;
        # prontidão do workflow de INCLUSAO não prova execução de ABERTURA.
        estado = "AGUARDANDO_HOMOLOGACAO_EXECUTOR_ABERTURA"
    return {"regra_id": rid, "player": player, "operacao": "ABERTURA",
            "estado": estado, "modo": modo, "executavel": False,
            "workflow_referencia": workflow.get("workflow"),
            "checkpoints_humanos": workflow.get("checkpoints_humanos") or [],
            "dados_recebidos": sorted(dados)}


def avaliar_aberturas_homologadas() -> list[dict]:
    """Inventário do motor de abertura, sem disparos externos."""
    return [avaliar_abertura(h["regra_id"]) for h in listar_homologacoes_mais_recentes()
            if str(h.get("regra_id") or "").startswith("ABERTURA-")]
