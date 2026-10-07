"""Matriz de prontidão operacional do EDDY.

Separa conhecimento, workflow, executor e autorização. Homologação prova que o
EDDY conhece o procedimento; não significa, por si só, que exista braço técnico
para executá-lo.
"""
from __future__ import annotations

from ednna.aprendizado_operacional import obter_regra_homologada, obter_autorizacao_motor
from ednna.workflows_inclusao import obter_workflow


def avaliar_prontidao_regra(player: str) -> dict:
    p = str(player or "").strip().upper()
    regra = obter_regra_homologada(p) or {}
    homologada = bool(regra)
    regra_id = str(regra.get("regra_id") or "")
    workflow = obter_workflow(p) or {}
    workflow_nome = str(workflow.get("workflow") or "NAO_CLASSIFICADO")
    prontidao_workflow = str(workflow.get("prontidao") or "SEM_WORKFLOW")
    executores_faltantes = list(workflow.get("executores_faltantes") or [])
    executor = str(workflow.get("executor") or "NAO_IMPLEMENTADO")
    autorizacao = obter_autorizacao_motor(regra_id) if regra_id else {}
    modo = str(autorizacao.get("modo") or "BLOQUEADA").upper()

    bloqueios = []
    if not homologada:
        bloqueios.append("CONHECIMENTO_NAO_HOMOLOGADO")
    if workflow_nome == "NAO_CLASSIFICADO" or prontidao_workflow == "SEM_WORKFLOW":
        bloqueios.append("WORKFLOW_NAO_CLASSIFICADO")
    if executores_faltantes or prontidao_workflow == "AGUARDANDO_EXECUTOR":
        bloqueios.append("EXECUTOR_NAO_IMPLEMENTADO")
    if not bool(workflow.get("ativa", True)):
        bloqueios.append("WORKFLOW_INATIVO")
    if modo not in {"ASSISTIDA", "AUTOMATICA"}:
        bloqueios.append("MOTOR_NAO_AUTORIZADO")

    if not homologada:
        estado = "APRENDER"
        proxima_acao = "Homologar conhecimento"
    elif "WORKFLOW_NAO_CLASSIFICADO" in bloqueios:
        estado = "DEFINIR_WORKFLOW"
        proxima_acao = "Classificar workflow"
    elif "EXECUTOR_NAO_IMPLEMENTADO" in bloqueios:
        estado = "IMPLEMENTAR_EXECUTOR"
        proxima_acao = "Implementar executor: " + ", ".join(executores_faltantes or [executor])
    elif "WORKFLOW_INATIVO" in bloqueios:
        estado = "ATIVAR_WORKFLOW"
        proxima_acao = "Ativar workflow"
    elif "MOTOR_NAO_AUTORIZADO" in bloqueios:
        estado = "AUTORIZAR_MOTOR"
        proxima_acao = "Autorizar motor"
    else:
        estado = "PRONTA"
        proxima_acao = "Operar conforme modo autorizado"

    return {
        "player": p,
        "regra_id": regra_id,
        "conhecimento": "HOMOLOGADA" if homologada else "NAO_HOMOLOGADA",
        "workflow": workflow_nome,
        "workflow_prontidao": prontidao_workflow,
        "executor": executor,
        "executores_faltantes": executores_faltantes,
        "modo_motor": modo,
        "estado_prontidao": estado,
        "bloqueios": bloqueios,
        "proxima_acao": proxima_acao,
        "pronta": estado == "PRONTA",
    }


def resumir_prontidao(players: list[str]) -> dict:
    itens = [avaliar_prontidao_regra(p) for p in dict.fromkeys(str(x or "").strip().upper() for x in players if str(x or "").strip())]
    estados = {}
    for item in itens:
        e = item["estado_prontidao"]
        estados[e] = estados.get(e, 0) + 1
    return {"total": len(itens), "estados": estados, "itens": itens}
