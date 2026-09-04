from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


CATALOGO_OPERACIONAL_PATH = Path(__file__).with_name(
    "catalogo_operacional.json"
)


def _texto(valor: Any) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    return str(valor).strip()


def carregar_catalogo_operacional() -> dict:
    try:
        return json.loads(
            CATALOGO_OPERACIONAL_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {
            "versao": "desconhecida",
            "modo": "OBSERVACAO",
            "regras": [],
        }


def _normalizar_origem(valor: str) -> str:
    return _texto(valor).upper()


def localizar_regra_operacional(
    linha: pd.Series | dict,
) -> dict | None:
    intencao = _texto(
        linha.get(
            "EDNNA - Intenção"
        )
    )

    subtipo = _texto(
        linha.get(
            "EDNNA - Subtipo"
        )
    )

    origem = _normalizar_origem(
        linha.get(
            "EDNNA - Origem operacional"
        )
        or linha.get(
            "Origem"
        )
    )

    catalogo = carregar_catalogo_operacional()

    for regra in catalogo.get(
        "regras",
        []
    ):
        if (
            _texto(
                regra.get(
                    "intencao"
                )
            )
            != intencao
        ):
            continue

        if (
            _texto(
                regra.get(
                    "subtipo"
                )
            )
            != subtipo
        ):
            continue

        origens_regra = {
            _normalizar_origem(
                item
            )
            for item in regra.get(
                "origens",
                []
            )
        }

        if origem not in origens_regra:
            continue

        return regra

    return None


def avaliar_acao(
    linha: pd.Series | dict,
) -> dict:
    chamado_id = _texto(
        linha.get(
            "#"
        )
    )

    cliente = _texto(
        linha.get(
            "Clientes"
        )
    )

    origem = _texto(
        linha.get(
            "EDNNA - Origem operacional"
        )
        or linha.get(
            "Origem"
        )
    )

    intencao = _texto(
        linha.get(
            "EDNNA - Intenção"
        )
    )

    subtipo = _texto(
        linha.get(
            "EDNNA - Subtipo"
        )
    )

    conflito = (
        _texto(
            linha.get(
                "EDNNA - Conflito de classificação"
            )
        ).upper()
        == "SIM"
    )

    dados_completos = (
        _texto(
            linha.get(
                "EDNNA - Dados operacionais completos"
            )
        ).upper()
        == "SIM"
    )

    regra = localizar_regra_operacional(
        linha
    )

    if regra is None:
        return {
            "estado": "SEM_REGRA",
            "rotulo": "Sem procedimento homologado",
            "apto_rascunho": False,
            "regra_id": "",
            "regra_nome": "",
            "motivo": (
                "Nenhuma regra operacional homologada para "
                f"{origem or 'esta origem'}."
            ),
            "cliente": cliente,
            "origem": origem,
            "intencao": intencao,
            "subtipo": subtipo,
        }

    if (
        regra.get(
            "bloqueia_conflito",
            True,
        )
        and conflito
    ):
        return {
            "estado": "BLOQUEADO_CONFLITO",
            "rotulo": "Revisão necessária",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": (
                "Há conflito entre a classificação operacional "
                "e o Tipo oficial do Redmine."
            ),
            "cliente": cliente,
            "origem": origem,
            "intencao": intencao,
            "subtipo": subtipo,
        }

    if (
        regra.get(
            "requer_dados_completos",
            True,
        )
        and not dados_completos
    ):
        faltantes = _texto(
            linha.get(
                "EDNNA - Campos faltantes"
            )
        )

        return {
            "estado": "DADOS_INCOMPLETOS",
            "rotulo": "Dados incompletos",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": (
                "Dados operacionais insuficientes"
                + (
                    f": {faltantes}."
                    if faltantes
                    else "."
                )
            ),
            "cliente": cliente,
            "origem": origem,
            "intencao": intencao,
            "subtipo": subtipo,
        }

    if not regra.get(
        "homologada_para_rascunho",
        False,
    ):
        return {
            "estado": "NAO_HOMOLOGADA",
            "rotulo": "Regra em observação",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": (
                "A regra ainda não foi homologada para geração "
                "de rascunho."
            ),
            "cliente": cliente,
            "origem": origem,
            "intencao": intencao,
            "subtipo": subtipo,
        }

    return {
        "estado": "APTO_RASCUNHO",
        "rotulo": "Pronto para rascunho",
        "apto_rascunho": True,
        "regra_id": regra.get("id", ""),
        "regra_nome": regra.get("nome", ""),
        "motivo": (
            "Dados completos e procedimento Pluxee "
            "homologado para rascunho assistido."
        ),
        "cliente": cliente,
        "origem": origem,
        "intencao": intencao,
        "subtipo": subtipo,
    }


def gerar_rascunho(
    linha: pd.Series | dict,
) -> dict:
    avaliacao = avaliar_acao(
        linha
    )

    if not avaliacao.get(
        "apto_rascunho"
    ):
        return {
            **avaliacao,
            "destinatarios": [],
            "cc": [],
            "assunto": "",
            "corpo": "",
        }

    regra = localizar_regra_operacional(
        linha
    ) or {}

    chamado_id = _texto(
        linha.get("#")
    )

    if chamado_id.endswith(".0"):
        chamado_id = chamado_id[:-2]

    cliente = _texto(
        linha.get(
            "Clientes"
        )
    ) or "Cliente não identificado"

    convenio = _texto(
        linha.get(
            "EDNNA - Convênio"
        )
    )

    referencia = _texto(
        linha.get(
            "EDNNA - Referência operacional"
        )
    )

    tipos = _texto(
        linha.get(
            "EDNNA - Tipos arquivo"
        )
    )

    arquivos_nsa = _texto(
        linha.get(
            "EDNNA - Arquivos/NSA"
        )
    )

    if not arquivos_nsa:
        nsa = _texto(
            linha.get(
                "EDNNA - NSA referência"
            )
        )

        arquivos_nsa = (
            f"{tipos or 'Arquivo'}: {nsa}"
            if nsa
            else ""
        )

    tipos_texto = (
        tipos
        or "arquivo(s)"
    )

    assunto = _texto(
        regra.get(
            "assunto_template"
        )
    ).format(
        cliente=cliente,
        chamado_id=chamado_id,
    )

    corpo = (
        "Bom dia, time Pluxee! Tudo bem?\n\n"
        f"Identificamos a ausência do(s) arquivo(s) de {tipos_texto} "
        f"para o cliente {cliente}.\n"
        f"Solicitamos, por gentileza, o reenvio dos arquivos faltantes "
        f"referentes ao período informado abaixo, para regularização "
        f"do processamento.\n\n"
        f"Convênio: {convenio}\n"
        f"Data: {referencia}\n"
        f"Último NSA conhecido: {arquivos_nsa}\n"
        f"Chamado Netunna: #{chamado_id}\n\n"
        "Agradecemos e permanecemos à disposição para quaisquer "
        "esclarecimentos.\n\n"
        "Atenciosamente,\n"
        "Equipe EDI Netunna"
    )

    return {
        **avaliacao,
        "destinatarios": list(
            regra.get(
                "destinatarios",
                []
            )
        ),
        "cc": list(
            regra.get(
                "cc_padrao",
                []
            )
        ),
        "assunto": assunto,
        "corpo": corpo,
        "canal": regra.get(
            "canal",
            "EMAIL",
        ),
        "executavel": bool(
            regra.get(
                "executavel",
                False,
            )
        ),
    }


def enriquecer_dataframe_com_acoes(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    if (
        frame is None
        or not isinstance(
            frame,
            pd.DataFrame,
        )
    ):
        return pd.DataFrame()

    resultado = frame.copy()

    if resultado.empty:
        return resultado

    estados = []
    regras = []
    motivos = []
    aptos = []

    for _, row in resultado.iterrows():
        avaliacao = avaliar_acao(
            row
        )

        estados.append(
            avaliacao.get(
                "rotulo",
                "",
            )
        )

        regras.append(
            avaliacao.get(
                "regra_id",
                "",
            )
        )

        motivos.append(
            avaliacao.get(
                "motivo",
                "",
            )
        )

        aptos.append(
            "SIM"
            if avaliacao.get(
                "apto_rascunho"
            )
            else "NÃO"
        )

    resultado[
        "EDNNA - Ação operacional"
    ] = estados

    resultado[
        "EDNNA - Regra operacional"
    ] = regras

    resultado[
        "EDNNA - Motivo ação"
    ] = motivos

    resultado[
        "EDNNA - Apto para rascunho"
    ] = aptos

    return resultado
