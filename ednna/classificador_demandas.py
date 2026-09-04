from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ednna.armazenamento import (
    listar_classificacoes_demandas,
    obter_classificacao_demanda,
    salvar_classificacao_demanda,
    salvar_metadado,
    agora_brasil_iso,
)
from ednna.sincronizador import normalizar_marca_alteracao


CATALOGO_PATH = Path(__file__).with_name(
    "catalogo_automacoes.json"
)


PADROES = {
    "RELACIONAMENTO_CREDENCIAMENTO": [
        (r"\bcredenciamento\b", 5),
        (r"\bcredenciar\b", 5),
        (r"\bafiliação\b|\bafiliacao\b", 4),
        (r"\brelacionamento\b", 4),
        (r"\bhabilita(?:ção|cao)\b", 3),
        (r"\badquirente\b", 1),
    ],
    "INCLUSAO_ESTABELECIMENTO": [
        (r"\binclus[aã]o\b.*\bestabelecimento\b", 6),
        (r"\badicionar\b.*\bestabelecimento\b", 5),
        (r"\bnovo estabelecimento\b", 5),
        (r"\bincluir\b.*\bloja\b", 4),
        (r"\binclus[aã]o\b.*\bloja\b", 4),
        (r"\bestabelecimento\b", 1),
    ],
    "FALTA_ARQUIVO": [
        (r"\bfalta\b.*\barquivo\b", 6),
        (r"\barquivo\b.*\bn[aã]o\b.*\b(?:recebido|chegou|dispon[ií]vel)\b", 6),
        (r"\bn[aã]o recebemos\b", 5),
        (r"\bn[aã]o chegou\b", 5),
        (r"\baus[eê]ncia\b.*\barquivo\b", 5),
        (r"\barquivo faltante\b", 6),
        (r"\bfaltante\b", 3),
    ],
    "REPROCESSAMENTO": [
        (r"\breprocess", 6),
        (r"\bprocessar novamente\b", 5),
        (r"\bprocessamento novamente\b", 5),
        (r"\breenvio\b", 3),
        (r"\breenviar\b", 3),
    ],
    "ALTERACAO_CADASTRAL": [
        (r"\baltera(?:ç[aã]o|cao)\b.*\bcadastr", 6),
        (r"\batualiza(?:ç[aã]o|cao)\b.*\bcadastr", 6),
        (r"\balterar\b.*\b(?:cnpj|filia(?:ç[aã]o|cao)|estabelecimento|loja)\b", 4),
        (r"\bcadastro\b", 2),
    ],
    "DUVIDA_ORIENTACAO": [
        (r"\bd[uú]vida\b", 5),
        (r"\borienta(?:ç[aã]o|cao)\b", 5),
        (r"\bcomo\b.*\b(?:fazer|proceder|funciona)\b", 3),
        (r"\besclarecimento\b", 4),
    ],
}


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return str(valor).strip()


def _normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def carregar_catalogo() -> dict:
    try:
        return json.loads(
            CATALOGO_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {
            "versao": "desconhecida",
            "modo": "OBSERVACAO",
            "regras": [],
        }


def _mapa_regras() -> dict[str, dict]:
    catalogo = carregar_catalogo()
    return {
        item.get("intencao", ""): item
        for item in catalogo.get("regras", [])
        if item.get("intencao")
    }


def classificar_linha(
    linha: pd.Series | dict,
) -> dict:
    get = linha.get

    campos = {
        "assunto": _texto(get("Assunto")),
        "descricao": _texto(get("Descrição")),
        "tipo": _texto(get("Tipo")),
        "origem": _texto(get("Origem")),
        "cliente": _texto(get("Clientes")),
    }

    texto = _normalizar_texto(
        " | ".join(
            valor
            for valor in campos.values()
            if valor
        )
    )

    pontuacoes: dict[str, int] = {}
    evidencias: dict[str, list[str]] = {}

    for intencao, padroes in PADROES.items():
        pontos = 0
        hits: list[str] = []

        for regex, peso in padroes:
            if re.search(regex, texto, flags=re.IGNORECASE):
                pontos += peso
                hits.append(regex)

        if pontos:
            pontuacoes[intencao] = pontos
            evidencias[intencao] = hits

    if not pontuacoes:
        return {
            "intencao": "NAO_CLASSIFICADO",
            "confianca": 0.0,
            "regra_candidata": "",
            "acao_sugerida": "Encaminhar para análise humana.",
            "executavel": False,
            "evidencias": [],
        }

    ranking = sorted(
        pontuacoes.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    melhor_intencao, melhor_pontuacao = ranking[0]
    segundo = ranking[1][1] if len(ranking) > 1 else 0

    # confiança heurística conservadora
    confianca = min(
        0.99,
        0.45
        + (melhor_pontuacao * 0.07)
        + (max(0, melhor_pontuacao - segundo) * 0.03),
    )

    if melhor_pontuacao < 4:
        return {
            "intencao": "NAO_CLASSIFICADO",
            "confianca": round(confianca, 2),
            "regra_candidata": "",
            "acao_sugerida": "Encaminhar para análise humana.",
            "executavel": False,
            "evidencias": evidencias.get(
                melhor_intencao,
                [],
            ),
        }

    regra = _mapa_regras().get(
        melhor_intencao,
        {},
    )

    return {
        "intencao": melhor_intencao,
        "confianca": round(confianca, 2),
        "regra_candidata": regra.get("id", ""),
        "acao_sugerida": regra.get(
            "acao_sugerida",
            "Analisar manualmente.",
        ),
        # v3.11 nunca executa automaticamente.
        "executavel": False,
        "evidencias": evidencias.get(
            melhor_intencao,
            [],
        ),
    }


def classificacao_precisa_atualizar(
    chamado_id: int,
    alterado_em: str,
) -> bool:
    atual = obter_classificacao_demanda(
        chamado_id
    )

    if atual is None:
        return True

    return (
        normalizar_marca_alteracao(
            atual.get("alterado_em_redmine")
        )
        != normalizar_marca_alteracao(
            alterado_em
        )
    )


def classificar_dataframe(
    frame: pd.DataFrame,
) -> dict:
    resultado = {
        "recebidos": 0,
        "classificados": 0,
        "reaproveitados": 0,
        "nao_classificados": 0,
        "erros": 0,
    }

    if (
        frame is None
        or not isinstance(frame, pd.DataFrame)
        or frame.empty
        or "#" not in frame.columns
    ):
        return resultado

    resultado["recebidos"] = len(frame)

    for _, row in frame.iterrows():
        try:
            chamado_id = int(
                float(row.get("#"))
            )
        except Exception:
            resultado["erros"] += 1
            continue

        alterado = normalizar_marca_alteracao(
            row.get("Alterado")
        )

        if not classificacao_precisa_atualizar(
            chamado_id,
            alterado,
        ):
            resultado["reaproveitados"] += 1
            continue

        try:
            item = classificar_linha(row)

            salvar_classificacao_demanda(
                chamado_id=chamado_id,
                alterado_em_redmine=alterado,
                intencao=item["intencao"],
                confianca=item["confianca"],
                regra_candidata=item["regra_candidata"],
                acao_sugerida=item["acao_sugerida"],
                executavel=False,
                evidencias=item["evidencias"],
            )

            resultado["classificados"] += 1

            if item["intencao"] == "NAO_CLASSIFICADO":
                resultado["nao_classificados"] += 1

        except Exception as exc:
            resultado["erros"] += 1
            print(
                "[EDNNA] Erro classificando demanda | "
                f"chamado={chamado_id} | erro={exc}",
                flush=True,
            )

    salvar_metadado(
        "ultima_classificacao_demandas",
        agora_brasil_iso(),
    )

    print(
        "[EDNNA] Classificação de demandas | "
        f"recebidos={resultado['recebidos']} | "
        f"classificados={resultado['classificados']} | "
        f"reaproveitados={resultado['reaproveitados']} | "
        f"nao_classificados={resultado['nao_classificados']} | "
        f"erros={resultado['erros']}",
        flush=True,
    )

    return resultado


def enriquecer_dataframe_com_classificacoes(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    if (
        frame is None
        or not isinstance(frame, pd.DataFrame)
    ):
        return pd.DataFrame()

    resultado = frame.copy()

    if resultado.empty:
        return resultado

    mapa = {
        int(item["chamado_id"]): item
        for item in listar_classificacoes_demandas()
        if item.get("chamado_id") is not None
    }

    intencoes = []
    confiancas = []
    regras = []
    acoes = []

    for _, row in resultado.iterrows():
        try:
            chamado_id = int(
                float(row.get("#"))
            )
        except Exception:
            chamado_id = -1

        item = mapa.get(chamado_id) or {}

        intencoes.append(
            item.get(
                "intencao",
                "NAO_CLASSIFICADO",
            )
        )
        confiancas.append(
            float(
                item.get(
                    "confianca",
                    0,
                )
                or 0
            )
        )
        regras.append(
            item.get(
                "regra_candidata",
                "",
            )
        )
        acoes.append(
            item.get(
                "acao_sugerida",
                "",
            )
        )

    resultado["EDNNA - Intenção"] = intencoes
    resultado["EDNNA - Confiança"] = confiancas
    resultado["EDNNA - Regra"] = regras
    resultado["EDNNA - Ação sugerida"] = acoes

    return resultado



def calcular_prontidao_automacao(frame: pd.DataFrame) -> pd.DataFrame:
    """Resume oportunidades de automação por intenção.

    A pontuação serve apenas para priorização. Não autoriza execução.
    """
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty or 'EDNNA - Intenção' not in frame.columns:
        return pd.DataFrame(columns=['Intenção','Chamados','Confiança média','Com regra candidata','Prontidão','Faixa'])

    base = frame.copy()
    if 'EDNNA - Confiança' not in base.columns:
        base['EDNNA - Confiança'] = 0.0
    if 'EDNNA - Regra' not in base.columns:
        base['EDNNA - Regra'] = ''

    linhas = []
    for intencao, grupo in base.groupby('EDNNA - Intenção', dropna=False):
        intencao = str(intencao if pd.notna(intencao) else 'NAO_CLASSIFICADO')
        total = len(grupo)
        confianca_media = float(pd.to_numeric(grupo['EDNNA - Confiança'], errors='coerce').fillna(0).mean())
        com_regra = int((grupo['EDNNA - Regra'].fillna('').astype(str).str.strip() != '').sum())
        pct_regra = (com_regra/total) if total else 0
        score_volume = min(1.0, total/20.0)
        score = score_volume*0.45 + confianca_media*0.40 + pct_regra*0.15
        if intencao == 'NAO_CLASSIFICADO': score = 0.0
        if score >= 0.80: faixa = 'Alta'
        elif score >= 0.60: faixa = 'Média'
        elif score > 0: faixa = 'Baixa'
        else: faixa = 'Não aplicável'
        linhas.append({'Intenção':intencao,'Chamados':total,'Confiança média':round(confianca_media,2),'Com regra candidata':com_regra,'Prontidão':round(score,2),'Faixa':faixa})

    resultado = pd.DataFrame(linhas)
    if resultado.empty: return resultado
    return resultado.sort_values(['Prontidão','Chamados','Confiança média'], ascending=[False,False,False]).reset_index(drop=True)


def resumo_oportunidades(frame: pd.DataFrame) -> dict:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return {'total':0,'reconhecidos':0,'nao_classificados':0,'com_regra':0,'alta_prontidao':0}
    total = len(frame)
    reconhecidos = int((frame['EDNNA - Intenção'].fillna('NAO_CLASSIFICADO').astype(str) != 'NAO_CLASSIFICADO').sum())
    com_regra = int((frame['EDNNA - Regra'].fillna('').astype(str).str.strip() != '').sum())
    prontidao = calcular_prontidao_automacao(frame)
    alta = int((prontidao['Faixa'] == 'Alta').sum()) if not prontidao.empty else 0
    return {'total':total,'reconhecidos':reconhecidos,'nao_classificados':total-reconhecidos,'com_regra':com_regra,'alta_prontidao':alta}
