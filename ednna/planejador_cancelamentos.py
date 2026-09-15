from __future__ import annotations

import re
from typing import Any

from ednna.contexto_relacionamentos import (
    analisar_contexto_cancelamento,
    buscar_issue_contexto,
)
from ednna.motor_acoes import gerar_rascunho
from ednna.orquestrador_cancelamentos import sincronizar_plano

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


def _eh_cnpj(valor: str) -> bool:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return len(digitos) == 14


def _normalizar_ec_getnet(valor: str) -> str:
    """Normaliza EC GETNET. CNPJ e texto puro nunca viram EC."""
    bruto = str(valor or "").strip()
    if not bruto or _eh_cnpj(bruto):
        return ""
    # Casos históricos como 1039197GETNET devem resultar em 1039197.
    m = re.match(r"^\s*(\d{5,12})(?:\s*GETNET)?\s*$", bruto, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    # Aceita somente identificador numérico plausível; palavras são descartadas.
    if re.fullmatch(r"\d{5,12}", bruto):
        return bruto
    return ""


def extrair_dados_getnet(issues: list[dict]) -> dict:
    """Separa ECs operacionais de CNPJs de contexto, sem contaminar com texto."""
    ecs: set[str] = set()
    cnpjs: set[str] = set()
    padroes = [
        r"\bEC\s*/\s*Conv[eê]nio\s*[:\-]?\s*([^\s,;|]+)",
        r"\bConv[eê]nio\s*[:\-]?\s*([^\s,;|]+)",
        r"\bEC\s*(?:[:\-]\s*|\s+)([^\s,;|]+)",
        r"\bEstabelecimento\s*[:\-]?\s*([^\s,;|]+)",
    ]
    cnpj_re = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
    for issue in issues:
        texto = _texto_issue(issue)
        cnpjs.update(cnpj_re.findall(texto))
        for padrao in padroes:
            for match in re.findall(padrao, texto, flags=re.IGNORECASE):
                valor = str(match or "").strip().strip(".,;:)")
                if _eh_cnpj(valor):
                    cnpjs.add(valor)
                    continue
                ec = _normalizar_ec_getnet(valor)
                if ec:
                    ecs.add(ec)
    return {"ecs": sorted(ecs, key=lambda x: (len(x), x)), "cnpjs": sorted(cnpjs)}


def _extrair_identificadores_getnet(issues: list[dict]) -> list[str]:
    return extrair_dados_getnet(issues)["ecs"]


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
        # Prioridade operacional: o chamado atual vem antes do histórico. Isso evita
        # perder um EC explicitamente informado na solicitação de cancelamento.
        try:
            issues.append(buscar_issue_contexto(int(chamado_id), force=force))
        except Exception:
            pass
        for fonte_id in fontes:
            try:
                issues.append(buscar_issue_contexto(fonte_id, force=force))
            except Exception:
                continue

        dados_getnet = extrair_dados_getnet(issues)
        identificadores = dados_getnet["ecs"]
        base["identificadores"] = identificadores
        base["cnpjs"] = dados_getnet["cnpjs"]

        if not identificadores:
            base.update({
                "status_plano": "DADOS_INCOMPLETOS",
                "rotulo": "Dados incompletos",
                "motivo": "Relacionamento GETNET localizado, mas nenhum EC/Convênio explicitamente identificado nas fontes históricas.",
            })
            itens.append(base)
            continue

        # Em cancelamento TOTAL, múltiplos ECs são válidos: todos devem compor o pedido.
        convenio_rascunho = ", ".join(identificadores)
        linha = _linha_sintetica_getnet(int(chamado_id), cliente, convenio_rascunho)
        rascunho = gerar_rascunho(linha)
        if rascunho.get("apto_rascunho"):
            base.update({
                "status_plano": "PRONTO_REVISAO",
                "rotulo": "Pronto para revisão",
                "rascunho": rascunho,
                "motivo": f"Procedimento GETNET homologado com {len(identificadores)} EC(s) reconstruído(s) do histórico.",
            })
        else:
            base.update({
                "status_plano": "DADOS_INCOMPLETOS",
                "rotulo": "Dados incompletos",
                "motivo": str(rascunho.get("motivo") or "O procedimento não ficou apto para rascunho."),
            })
        itens.append(base)

    # v3.28.5: persiste uma etapa por player. Ao homologar uma nova regra no catálogo,
    # a próxima reconstrução promove automaticamente a etapa correspondente.
    sincronizar_plano(int(chamado_id), itens)

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
