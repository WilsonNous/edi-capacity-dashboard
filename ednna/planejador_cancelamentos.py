from __future__ import annotations

import re
from typing import Any

from ednna.contexto_relacionamentos import (
    analisar_contexto_cancelamento,
    buscar_issue_contexto,
)
from ednna.motor_acoes import gerar_rascunho

# ============================================================
# EDNNA — PLANEJADOR DE CANCELAMENTOS
# v3.25
#
# SOMENTE PREPARAÇÃO. Não envia e-mail e não altera Redmine.
# Cada player precisa de procedimento homologado no catálogo.
# ============================================================


def _texto_issue(issue: dict) -> str:
    partes = [str(issue.get("subject") or ""), str(issue.get("description") or "")]
    for journal in issue.get("journals", []) or []:
        if journal.get("notes"):
            partes.append(str(journal["notes"]))
    return "\n".join(partes)


def _extrair_identificadores_getnet(issues: list[dict]) -> list[str]:
    """Extrai EC/Convênio somente quando explicitamente rotulado no histórico."""
    valores: set[str] = set()
    padroes = [
        r"\bEC\s*/\s*Conv[eê]nio\s*[:\-]?\s*([A-Za-z0-9._/-]+)",
        r"\bConv[eê]nio\s*[:\-]?\s*([A-Za-z0-9._/-]+)",
        r"\bEC\s*(?:[:\-]\s*|\s+)([0-9][A-Za-z0-9._/-]*)",
        r"\bEstabelecimento\s*[:\-]?\s*([A-Za-z0-9._/-]+)",
    ]
    for issue in issues:
        texto = _texto_issue(issue)
        for padrao in padroes:
            for match in re.findall(padrao, texto, flags=re.IGNORECASE):
                valor = str(match or "").strip().strip(".,;:)")
                if valor:
                    valores.add(valor)
    return sorted(valores)


def _linha_sintetica_getnet(chamado_id: int, cliente: str, convenio: str) -> dict[str, Any]:
    return {
        "#": int(chamado_id),
        "Clientes": cliente,
        "Origem": "GETNET",
        "EDNNA - Origem operacional": "GETNET",
        "EDNNA - Intenção": "CANCELAMENTO_TRAFEGO",
        "EDNNA - Subtipo": "CANCELAMENTO_TOTAL",
        "EDNNA - Convênio": convenio,
        "EDNNA - Conflito de classificação": "NÃO",
        "EDNNA - Dados operacionais completos": "SIM" if convenio else "NÃO",
    }


def preparar_plano_cancelamento(chamado_id: int, *, force: bool = False) -> dict:
    contexto = analisar_contexto_cancelamento(int(chamado_id), force=force)
    cliente = str(contexto.get("cliente") or "").strip()
    itens: list[dict] = []

    for rel in contexto.get("relacionamentos", []):
        player = str(rel.get("player") or "").strip().upper()
        estado_hist = str(rel.get("estado") or "")
        fontes = [int(x) for x in rel.get("fontes", []) if x]

        base = {
            "player": player,
            "estado_historico": estado_hist,
            "fontes": fontes,
            "status_plano": "PROCEDIMENTO_NAO_HOMOLOGADO",
            "rotulo": "Procedimento ainda não homologado",
            "identificadores": [],
            "rascunho": None,
            "motivo": "Ainda não há procedimento de cancelamento homologado para este player.",
        }

        if estado_hist == "CANCELADO_CONFIRMADO":
            base.update({
                "status_plano": "JA_CANCELADO",
                "rotulo": "Já cancelado",
                "motivo": f"Cancelamento anterior confirmado no chamado #{rel.get('cancelamento_anterior')}.",
            })
            itens.append(base)
            continue

        if estado_hist != "RELACIONAMENTO_LOCALIZADO":
            base.update({
                "status_plano": "DADOS_INCOMPLETOS",
                "rotulo": "Dados históricos insuficientes",
                "motivo": "Não foi possível confirmar um relacionamento operacional no histórico.",
            })
            itens.append(base)
            continue

        # v3.25: primeiro procedimento homologado = GETNET.
        if player != "GETNET":
            itens.append(base)
            continue

        issues = []
        for fonte_id in fontes:
            try:
                issues.append(buscar_issue_contexto(fonte_id, force=force))
            except Exception:
                continue

        identificadores = _extrair_identificadores_getnet(issues)
        base["identificadores"] = identificadores

        if not identificadores:
            base.update({
                "status_plano": "DADOS_INCOMPLETOS",
                "rotulo": "Dados incompletos",
                "motivo": "Relacionamento GETNET localizado, mas nenhum EC/Convênio explicitamente identificado nas fontes históricas.",
            })
            itens.append(base)
            continue

        if len(identificadores) > 1:
            base.update({
                "status_plano": "CONFLITO_HISTORICO",
                "rotulo": "Revisão necessária",
                "motivo": "Foram encontrados múltiplos ECs/Convênios no histórico. A EDNNA não escolheu um automaticamente.",
            })
            itens.append(base)
            continue

        linha = _linha_sintetica_getnet(int(chamado_id), cliente, identificadores[0])
        rascunho = gerar_rascunho(linha)
        if rascunho.get("apto_rascunho"):
            base.update({
                "status_plano": "PRONTO_REVISAO",
                "rotulo": "Pronto para revisão",
                "rascunho": rascunho,
                "motivo": "Procedimento GETNET homologado e dados mínimos reconstruídos do histórico.",
            })
        else:
            base.update({
                "status_plano": "DADOS_INCOMPLETOS",
                "rotulo": "Dados incompletos",
                "motivo": str(rascunho.get("motivo") or "O procedimento não ficou apto para rascunho."),
            })
        itens.append(base)

    return {
        "chamado_id": int(chamado_id),
        "cliente": cliente,
        "escopo": contexto.get("escopo"),
        "blueprint_id": contexto.get("blueprint_id"),
        "itens": itens,
        "modo": "RASCUNHO_ASSISTIDO_SEM_ENVIO",
        "resumo": {
            "prontos": sum(1 for x in itens if x["status_plano"] == "PRONTO_REVISAO"),
            "incompletos": sum(1 for x in itens if x["status_plano"] == "DADOS_INCOMPLETOS"),
            "conflitos": sum(1 for x in itens if x["status_plano"] == "CONFLITO_HISTORICO"),
            "ja_cancelados": sum(1 for x in itens if x["status_plano"] == "JA_CANCELADO"),
            "sem_procedimento": sum(1 for x in itens if x["status_plano"] == "PROCEDIMENTO_NAO_HOMOLOGADO"),
        },
    }
