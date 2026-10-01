from __future__ import annotations

"""EDNNA 3.34.15 — prática assistida de Abertura de Relacionamento.

A regra homologada continua sendo a autoridade. Este módulo apenas transforma
uma proposta de abertura em um plano operacional seguro: a EDNNA executa o que
é dela e encaminha checkpoints externos para o humano.
"""
from typing import Iterable

from ednna.escola_continua import matricular, registrar_evidencia
from ednna.homologacao import estado_regra, regra_pode_executar

ESTADO_ASSISTIDO = "EM_OBSERVACAO"
DESTINO_EDNNA = "CONTINUIDADE_EDNNA"
DESTINO_HUMANO = "PRECISO_DE_VOCE"
DESTINO_EXTERNO = "AGUARDANDO_CONDICAO_EXTERNA"

CHECKPOINTS_HUMANOS = {
    "EXECUTAR_API_PORTAL",
    "ASSINATURA_DOCUMENTO",
    "ATUALIZAR_PLANILHA",
    "VALIDAR_ARQUIVOS",
    "DECISAO_AMBIGUA",
}


def regra_abertura_ativa(regra_id: str) -> bool:
    """Somente regras homologadas ATIVA/EM_OBSERVACAO podem praticar."""
    return regra_pode_executar(str(regra_id or "").strip())


def plano_assistido(regra: dict) -> dict:
    """Monta plano sem executar efeitos externos.

    Mantém a fronteira professor/aluna explícita e reutiliza as etapas já
    aprendidas pelo minerador, evitando um segundo motor de regras.
    """
    rid = str(regra.get("regra_id") or "").strip()
    player = str(regra.get("player") or "").strip()
    homologacao = estado_regra(rid) if rid else None
    autorizado = bool(homologacao and homologacao.get("estado") in ("ATIVA", ESTADO_ASSISTIDO))
    etapas = []
    for etapa in list(regra.get("etapas") or []) + list(regra.get("politicas_homologadas") or []):
        codigo = str(etapa.get("codigo") or "").strip()
        responsavel = str(etapa.get("responsavel") or "EDNNA").upper()
        humano = responsavel == "CHECKPOINT_HUMANO" or codigo in CHECKPOINTS_HUMANOS
        etapas.append({**etapa, "destino_operacional": DESTINO_HUMANO if humano else DESTINO_EDNNA})
    return {
        "regra_id": rid,
        "player": player,
        "autorizada": autorizado,
        "modo": "ATIVO_ASSISTIDO" if autorizado else "SOMENTE_APRENDIZADO",
        "estado_homologacao": (homologacao or {}).get("estado"),
        "etapas": etapas,
    }


def ativar_pratica_assistida(regra: dict) -> dict:
    """Matricula regra homologada e devolve o plano de prática."""
    plano = plano_assistido(regra)
    if not plano["autorizada"]:
        return plano
    matricular(plano["regra_id"], plano["player"])
    return plano


def registrar_resultado_producao(regra_id: str, *, sucesso: bool, divergente: bool = False) -> None:
    """Produção real alimenta a Escola Contínua sem auto-homologar a regra."""
    registrar_evidencia(str(regra_id or "").strip(), divergente=bool(divergente or not sucesso))


def decidir_destino_retorno(*, exige_acao_humana: bool = False,
                            depende_evento_externo: bool = False,
                            ednna_pode_continuar: bool = False) -> str:
    """Classificação operacional conservadora para retornos interpretados."""
    if exige_acao_humana:
        return DESTINO_HUMANO
    if depende_evento_externo:
        return DESTINO_EXTERNO
    if ednna_pode_continuar:
        return DESTINO_EDNNA
    return DESTINO_HUMANO


def resumir_planos(regras: Iterable[dict]) -> dict:
    planos = [plano_assistido(r) for r in regras]
    return {
        "total": len(planos),
        "ativas_assistidas": sum(1 for p in planos if p["autorizada"]),
        "somente_aprendizado": sum(1 for p in planos if not p["autorizada"]),
        "planos": planos,
    }
