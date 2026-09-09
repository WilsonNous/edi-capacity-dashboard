from __future__ import annotations

import json
import re
import unicodedata
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


def _sem_acentos(valor: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", _texto(valor))
        if unicodedata.category(c) != "Mn"
    )


def _normalizar(valor: str) -> str:
    return re.sub(r"\s+", " ", _sem_acentos(valor).upper().strip())


def carregar_catalogo_operacional() -> dict:
    try:
        return json.loads(
            CATALOGO_OPERACIONAL_PATH.read_text(encoding="utf-8")
        )
    except Exception:
        return {"versao": "desconhecida", "modo": "OBSERVACAO", "regras": []}


def _texto_completo_linha(linha: pd.Series | dict) -> str:
    return " | ".join(
        _texto(item)
        for item in [
            linha.get("Clientes"),
            linha.get("Origem"),
            linha.get("EDNNA - Origem operacional"),
            linha.get("Tipo"),
            linha.get("Assunto"),
            linha.get("Descrição"),
        ]
        if _texto(item)
    )


def _cliente_casa(regra: dict, cliente: str) -> bool:
    clientes = regra.get("clientes", [])

    if not clientes:
        return True

    cliente_norm = _normalizar(cliente)

    return any(
        _normalizar(item) in cliente_norm
        or cliente_norm in _normalizar(item)
        for item in clientes
    )


def _origem_casa(regra: dict, origem: str) -> bool:
    origens = regra.get("origens", [])

    if not origens:
        return True

    origem_norm = _normalizar(origem)

    return any(
        origem_norm == _normalizar(item)
        or _normalizar(item) in origem_norm
        for item in origens
    )


def _tem_excecao(regra: dict, linha: pd.Series | dict) -> tuple[bool, str]:
    texto = _normalizar(_texto_completo_linha(linha))

    for excecao in regra.get("excecoes_texto", []):
        if _normalizar(excecao) in texto:
            return True, excecao

    origem = _normalizar(
        linha.get("EDNNA - Origem operacional")
        or linha.get("Origem")
    )

    if "SANTANDER" in origem and re.search(r"\bPIX\b", texto):
        return True, "Santander PIX"

    return False, ""


def _localizar_regra_operacional_base(linha: pd.Series | dict) -> dict | None:
    intencao = _texto(linha.get("EDNNA - Intenção"))
    subtipo = _texto(linha.get("EDNNA - Subtipo"))
    origem = _texto(
        linha.get("EDNNA - Origem operacional")
        or linha.get("Origem")
    )
    cliente = _texto(linha.get("Clientes"))

    for regra in carregar_catalogo_operacional().get("regras", []):
        if _texto(regra.get("intencao")) != intencao:
            continue
        if _texto(regra.get("subtipo")) != subtipo:
            continue
        if not _cliente_casa(regra, cliente):
            continue
        if not _origem_casa(regra, origem):
            continue
        return regra

    return None


def _dados_disponiveis(linha: pd.Series | dict) -> dict[str, bool]:
    return {
        "cliente": bool(_texto(linha.get("Clientes"))),
        "origem": bool(_texto(
            linha.get("EDNNA - Origem operacional")
            or linha.get("Origem")
        )),
        "referencia": bool(_texto(
            linha.get("EDNNA - Referência operacional")
            or linha.get("EDNNA - Referência")
        )),
        "tipo_arquivo": bool(_texto(linha.get("EDNNA - Tipos arquivo"))),
        "convenio": bool(_texto(linha.get("EDNNA - Convênio"))),
        "nsa": bool(_texto(linha.get("EDNNA - NSA referência"))),
    }


def _campos_faltantes_regra(regra: dict, linha: pd.Series | dict) -> list[str]:
    disponiveis = _dados_disponiveis(linha)
    nomes = {
        "cliente": "Cliente",
        "origem": "Banco/origem",
        "referencia": "Data/período",
        "tipo_arquivo": "Tipo de arquivo",
        "convenio": "Convênio",
        "nsa": "Último NSA conhecido",
    }

    return [
        nomes.get(campo, campo)
        for campo in regra.get("campos_obrigatorios", [])
        if not disponiveis.get(campo, False)
    ]


def avaliar_acao(linha: pd.Series | dict) -> dict:
    cliente = _texto(linha.get("Clientes"))
    origem = _texto(
        linha.get("EDNNA - Origem operacional")
        or linha.get("Origem")
    )
    intencao = _texto(linha.get("EDNNA - Intenção"))
    subtipo = _texto(linha.get("EDNNA - Subtipo"))
    conflito = (
        _texto(linha.get("EDNNA - Conflito de classificação")).upper()
        == "SIM"
    )

    regra = localizar_regra_operacional(linha)
    base = {
        "cliente": cliente,
        "origem": origem,
        "intencao": intencao,
        "subtipo": subtipo,
    }

    if regra is None:
        return {
            **base,
            "estado": "SEM_REGRA",
            "rotulo": "Sem procedimento homologado",
            "apto_rascunho": False,
            "regra_id": "",
            "regra_nome": "",
            "motivo": (
                f"Nenhuma regra operacional homologada para "
                f"{cliente or 'este cliente'} / {origem or 'esta origem'}."
            ),
        }

    tem_excecao, excecao = _tem_excecao(regra, linha)

    if tem_excecao:
        return {
            **base,
            "estado": "EXCECAO_REGRA",
            "rotulo": "Exceção da regra",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": f"Chamado excluído deste procedimento: {excecao}.",
        }

    if regra.get("bloqueia_conflito", True) and conflito:
        return {
            **base,
            "estado": "BLOQUEADO_CONFLITO",
            "rotulo": "Revisão necessária",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": "Há conflito entre a classificação operacional e o Tipo oficial do Redmine.",
        }

    campos_obrigatorios = regra.get("campos_obrigatorios", [])

    if campos_obrigatorios:
        faltantes = _campos_faltantes_regra(regra, linha)

        if faltantes:
            return {
                **base,
                "estado": "DADOS_INCOMPLETOS",
                "rotulo": "Dados incompletos",
                "apto_rascunho": False,
                "regra_id": regra.get("id", ""),
                "regra_nome": regra.get("nome", ""),
                "motivo": "Dados necessários para esta regra: " + ", ".join(faltantes) + ".",
            }

    elif (
        regra.get("requer_dados_completos", True)
        and _texto(linha.get("EDNNA - Dados operacionais completos")).upper()
        != "SIM"
    ):
        return {
            **base,
            "estado": "DADOS_INCOMPLETOS",
            "rotulo": "Dados incompletos",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": "Dados operacionais insuficientes para esta regra.",
        }

    if not regra.get("homologada_para_rascunho", False):
        return {
            **base,
            "estado": "NAO_HOMOLOGADA",
            "rotulo": "Regra em observação",
            "apto_rascunho": False,
            "regra_id": regra.get("id", ""),
            "regra_nome": regra.get("nome", ""),
            "motivo": "A regra ainda não foi homologada para geração de rascunho.",
        }

    return {
        **base,
        "estado": "APTO_RASCUNHO",
        "rotulo": "Pronto para rascunho",
        "apto_rascunho": True,
        "regra_id": regra.get("id", ""),
        "regra_nome": regra.get("nome", ""),
        "motivo": (
            "Dados mínimos da regra identificados e procedimento homologado "
            "para rascunho assistido."
        ),
    }


def gerar_rascunho(linha: pd.Series | dict) -> dict:
    avaliacao = avaliar_acao(linha)

    if not avaliacao.get("apto_rascunho"):
        return {
            **avaliacao,
            "destinatarios": [],
            "cc": [],
            "assunto": "",
            "corpo": "",
        }

    regra = localizar_regra_operacional(linha) or {}
    chamado_id = _texto(linha.get("#"))

    if chamado_id.endswith(".0"):
        chamado_id = chamado_id[:-2]

    cliente = _texto(linha.get("Clientes")) or "Cliente não identificado"
    origem = _texto(
        linha.get("EDNNA - Origem operacional")
        or linha.get("Origem")
    ) or "Origem não identificada"
    convenio = _texto(linha.get("EDNNA - Convênio"))
    referencia = _texto(
        linha.get("EDNNA - Referência operacional")
        or linha.get("EDNNA - Referência")
    )
    tipos = _texto(linha.get("EDNNA - Tipos arquivo"))
    nsa = _texto(linha.get("EDNNA - NSA referência"))

    assunto = _texto(regra.get("assunto_template")).format(
        cliente=cliente,
        origem=origem,
        chamado_id=chamado_id,
    )

    if regra.get("id") == "FALTA-BANCO-SIMREDE-001":
        linhas = [
            f"Banco: {origem}",
            f"Referência: {referencia}",
        ]

        if tipos:
            linhas.append(f"Tipo/Arquivo: {tipos}")
        if convenio:
            linhas.append(f"Convênio: {convenio}")
        if nsa:
            linhas.append(f"Último NSA conhecido: {nsa}")

        linhas.append(f"Chamado Netunna: #{chamado_id}")

        corpo = (
            f"{regra.get('saudacao', 'Olá, Time SIMREDE, tudo bem?')}\n\n"
            "Identificamos a ausência de arquivo(s) bancário(s) "
            "no processamento da SIM REDE.\n\n"
            + "\n".join(linhas)
            + "\n\n"
            "Poderiam, por gentileza, verificar e encaminhar os arquivos "
            "faltantes para regularização do processamento?\n\n"
            "Agradecemos e permanecemos à disposição para quaisquer esclarecimentos.\n\n"
            "Atenciosamente,\n"
            "Equipe EDI Netunna"
        )

    else:
        arquivos_nsa = _texto(linha.get("EDNNA - Arquivos/NSA"))

        if not arquivos_nsa and nsa:
            arquivos_nsa = f"{tipos or 'Arquivo'}: {nsa}"

        corpo = (
            "Olá, Time Pluxee, tudo bem?\n\n"
            f"Identificamos a ausência do(s) arquivo(s) de {tipos or 'arquivo(s)'} "
            f"para o cliente {cliente}.\n"
            "Solicitamos, por gentileza, o reenvio dos arquivos faltantes "
            "referentes ao período informado abaixo, para regularização do processamento.\n\n"
            f"Convênio: {convenio}\n"
            f"Data: {referencia}\n"
            f"Último NSA conhecido: {arquivos_nsa}\n"
            f"Chamado Netunna: #{chamado_id}\n\n"
            "Agradecemos e permanecemos à disposição para quaisquer esclarecimentos.\n\n"
            "Atenciosamente,\n"
            "Equipe EDI Netunna"
        )

    return {
        **avaliacao,
        "remetente": str(
            regra.get(
                "remetente",
                "edi@netunna.com.br",
            )
            or "edi@netunna.com.br"
        ),
        "destinatarios": list(regra.get("destinatarios", [])),
        "cc": list(regra.get("cc_padrao", [])),
        "assunto": assunto,
        "corpo": corpo,
        "canal": regra.get("canal", "EMAIL"),
        "executavel": bool(regra.get("executavel", False)),
        "prazo_resposta_dias_uteis": int(
            regra.get("prazo_resposta_dias_uteis", 0) or 0
        ),
    }


def enriquecer_dataframe_com_acoes(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()

    resultado = frame.copy()

    if resultado.empty:
        return resultado

    estados, regras, motivos, aptos = [], [], [], []

    for _, row in resultado.iterrows():
        avaliacao = avaliar_acao(row)
        estados.append(avaliacao.get("rotulo", ""))
        regras.append(avaliacao.get("regra_id", ""))
        motivos.append(avaliacao.get("motivo", ""))
        aptos.append("SIM" if avaliacao.get("apto_rascunho") else "NÃO")

    resultado["EDNNA - Ação operacional"] = estados
    resultado["EDNNA - Regra operacional"] = regras
    resultado["EDNNA - Motivo ação"] = motivos
    resultado["EDNNA - Apto para rascunho"] = aptos

    return resultado


# ============================================================
# v3.21.2 — especialização SIM REDE / ITAU
# ============================================================

def _texto_busca_acao_itau(linha) -> str:
    partes = []
    for campo in (
        "Assunto",
        "Descrição",
        "Descricao",
        "EDNNA - Ação sugerida",
        "EDNNA - Referência operacional",
    ):
        try:
            valor = linha.get(campo, "")
        except Exception:
            valor = ""
        if valor is not None:
            partes.append(str(valor))
    return " ".join(partes).casefold()


def _eh_itau_ativacao_retroativo(linha) -> bool:
    cliente = str(
        linha.get("Clientes", linha.get("Cliente", "")) or ""
    ).strip().casefold()

    origem = str(
        linha.get(
            "EDNNA - Origem operacional",
            linha.get("Origem", ""),
        )
        or ""
    ).strip().casefold()

    texto = _texto_busca_acao_itau(linha)

    eh_simrede = (
        "sim rede" in cliente
        or "simrede" in cliente
        or "sim rede" in texto
        or "simrede" in texto
    )

    eh_itau = (
        origem in {"itau", "itaú"}
        or " itau " in f" {texto} "
        or " itaú " in f" {texto} "
    )

    pede_diario = any(
        termo in texto
        for termo in (
            "ativação do envio diário",
            "ativacao do envio diario",
            "envio diário",
            "envio diario",
            "restabelecido",
            "restabelecimento",
        )
    )

    pede_retroativo = any(
        termo in texto
        for termo in (
            "retroativo",
            "desde ",
            "a partir de",
        )
    )

    return eh_simrede and eh_itau and pede_diario and pede_retroativo


def _regra_especifica_itau(linha):
    if not _eh_itau_ativacao_retroativo(linha):
        return None

    catalogo = carregar_catalogo_operacional()

    for regra in catalogo.get("regras", []):
        if regra.get("id") == "FALTA-BANCO-SIMREDE-ITAU-ATIVACAO-001":
            return regra

    return None


def localizar_regra_operacional(linha):
    especifica = _regra_especifica_itau(linha)

    if especifica is not None:
        return especifica

    return _localizar_regra_operacional_base(linha)
