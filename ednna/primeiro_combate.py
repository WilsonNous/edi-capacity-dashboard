from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import pandas as pd

from redmine_api import buscar_detalhes_chamado


# ============================================================
# EDNNA — INTELIGÊNCIA OPERACIONAL EDI
# Módulo: Primeiro Combate
# ============================================================

STATUS_PRIMEIRO_COMBATE = os.getenv(
    "EDNNA_STATUS_PRIMEIRO_COMBATE",
    "Aberto",
)

MAX_WORKERS = max(
    1,
    int(os.getenv("EDNNA_MAX_WORKERS", "2")),
)


# ============================================================
# CONFIGURAÇÃO DE AUTORES
# ============================================================
#
# EDNNA_AUTORES_EDI
#
# Opcional.
#
# Exemplo:
#
# EDNNA_AUTORES_EDI=Wilson Martins,João Silva,Maria Souza
#
# Se estiver vazio:
# qualquer comentário humano diferente dos autores ignorados
# será considerado atuação.
#
# Posteriormente poderemos configurar exatamente os usuários
# da equipe EDI.
# ============================================================

AUTORES_EDI = {
    nome.strip().casefold()
    for nome in os.getenv(
        "EDNNA_AUTORES_EDI",
        "",
    ).split(",")
    if nome.strip()
}


# ============================================================
# AUTORES IGNORADOS
# ============================================================
#
# Evita considerar uma atuação feita pela própria EDNNA
# como primeiro combate humano.
#
# Pode futuramente incluir usuários de integração/bots.
# ============================================================

AUTORES_IGNORADOS = {
    nome.strip().casefold()
    for nome in os.getenv(
        "EDNNA_IGNORAR_AUTORES",
        "EDNNA",
    ).split(",")
    if nome.strip()
}


# ============================================================
# CAMPOS DO REDMINE QUE REPRESENTAM ATUAÇÃO RELEVANTE
# ============================================================
#
# Alterações puramente administrativas não necessariamente
# representam um primeiro atendimento.
#
# Estes campos são considerados relevantes inicialmente.
# ============================================================

CAMPOS_RELEVANTES = {
    "status_id",
    "assigned_to_id",
    "priority_id",
    "done_ratio",
    "due_date",
}


# ============================================================
# FUNÇÕES BÁSICAS
# ============================================================

def normalizar_texto(valor: Any) -> str:
    """
    Converte qualquer valor simples em texto limpo.
    """

    if valor is None:
        return ""

    return str(valor).strip()


def normalizar_nome(valor: Any) -> str:
    """
    Normaliza nomes para comparação.
    """

    return normalizar_texto(valor).casefold()


def eh_estado_aberto(valor: Any) -> bool:
    """
    Retorna True somente quando o nome real do estado é 'Aberto'.

    Importante:
    No Redmine, status_id='open' representa todos os chamados
    que ainda não estão fechados.

    Para o primeiro combate da EDNNA queremos somente chamados
    cujo Estado real seja 'Aberto'.
    """

    return (
        normalizar_texto(valor).casefold()
        == STATUS_PRIMEIRO_COMBATE.casefold()
    )


# ============================================================
# FILTRO DO DATAFRAME
# ============================================================

def filtrar_estado_aberto_dataframe(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recebe o DataFrame já carregado pelo dashboard
    e retorna somente os chamados cujo Estado seja 'Aberto'.

    Esta função NÃO consulta novamente o Redmine.
    """

    if frame is None:
        return pd.DataFrame()

    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()

    if frame.empty:
        return frame.copy()

    if "Estado" not in frame.columns:
        return frame.iloc[0:0].copy()

    mascara = (
        frame["Estado"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq(STATUS_PRIMEIRO_COMBATE.casefold())
    )

    return frame[mascara].copy()


# ============================================================
# RESUMO DA FILA BRUTA
# ============================================================

def resumo_fila_primeiro_combate(
    frame: pd.DataFrame,
) -> dict:
    """
    Gera resumo da fila inicial da EDNNA.

    Neste ponto ainda NÃO analisamos journals.
    """

    fila = filtrar_estado_aberto_dataframe(frame)

    total = len(fila)

    if "Tempo em aberto (dias)" in fila.columns:
        mais_1_dia = int(
            (
                pd.to_numeric(
                    fila["Tempo em aberto (dias)"],
                    errors="coerce",
                ).fillna(0)
                >= 1
            ).sum()
        )
    else:
        mais_1_dia = 0

    if "Prioridade crítica" in fila.columns:
        criticos = int(
            fila["Prioridade crítica"]
            .fillna(False)
            .astype(bool)
            .sum()
        )
    else:
        criticos = 0

    if "Atribuído a" in fila.columns:
        sem_responsavel = int(
            fila["Atribuído a"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )
    else:
        sem_responsavel = 0

    return {
        "total_estado_aberto": total,
        "ha_1_dia_ou_mais": mais_1_dia,
        "prioridade_critica": criticos,
        "sem_responsavel": sem_responsavel,
    }


# ============================================================
# JOURNALS — UTILIDADES
# ============================================================

def _autor_journal(journal: dict) -> str:
    """
    Obtém o nome do autor de um journal.
    """

    usuario = journal.get("user") or {}

    return normalizar_texto(
        usuario.get("name")
    )


def _journal_tem_nota(journal: dict) -> bool:
    """
    Retorna True quando o journal possui comentário.
    """

    notas = normalizar_texto(
        journal.get("notes")
    )

    return bool(notas)


def _journal_tem_alteracao_relevante(
    journal: dict,
) -> bool:
    """
    Verifica se o journal contém alguma alteração que
    consideramos atuação operacional relevante.
    """

    detalhes = journal.get("details") or []

    for detalhe in detalhes:

        nome_campo = normalizar_texto(
            detalhe.get("name")
        )

        if nome_campo in CAMPOS_RELEVANTES:
            return True

    return False


def _autor_deve_ser_ignorado(
    autor: str,
) -> bool:
    """
    Verifica se determinado autor deve ser ignorado.
    """

    autor_normalizado = normalizar_nome(autor)

    if not autor_normalizado:
        return True

    return autor_normalizado in AUTORES_IGNORADOS


def _autor_eh_edi(
    autor: str,
) -> bool:
    """
    Verifica se o autor pertence à equipe EDI.

    Se EDNNA_AUTORES_EDI estiver vazio, qualquer autor
    humano não ignorado será aceito nesta primeira fase.
    """

    autor_normalizado = normalizar_nome(autor)

    if not autor_normalizado:
        return False

    if _autor_deve_ser_ignorado(autor):
        return False

    if not AUTORES_EDI:
        return True

    return autor_normalizado in AUTORES_EDI


def _journal_representa_atuacao(
    journal: dict,
) -> bool:
    """
    Decide se um journal representa atuação válida.

    Consideramos inicialmente:
    - comentário;
    - ou alteração relevante;
    - realizada por autor aceito.
    """

    autor = _autor_journal(journal)

    if not _autor_eh_edi(autor):
        return False

    if _journal_tem_nota(journal):
        return True

    if _journal_tem_alteracao_relevante(journal):
        return True

    return False


# ============================================================
# DATA DO REDMINE
# ============================================================

def _parse_data_redmine(
    valor: Any,
) -> datetime | None:
    """
    Converte datas ISO retornadas pelo Redmine.

    Exemplos:
    2026-09-03T12:30:25Z
    2026-09-03T12:30:25+00:00
    """

    texto = normalizar_texto(valor)

    if not texto:
        return None

    try:

        if texto.endswith("Z"):
            texto = texto[:-1] + "+00:00"

        return datetime.fromisoformat(texto)

    except (ValueError, TypeError):
        return None


# ============================================================
# LOCALIZAR PRIMEIRA ATUAÇÃO
# ============================================================

def localizar_primeira_atuacao(
    journals: list[dict],
) -> dict | None:
    """
    Percorre os journals em ordem cronológica e retorna
    a primeira atuação considerada válida.
    """

    if not journals:
        return None

    journals_ordenados = sorted(
        journals,
        key=lambda j: (
            _parse_data_redmine(
                j.get("created_on")
            )
            or datetime.max.replace(tzinfo=None)
        ).isoformat(),
    )

    for journal in journals_ordenados:

        if not _journal_representa_atuacao(
            journal
        ):
            continue

        autor = _autor_journal(journal)

        notas = normalizar_texto(
            journal.get("notes")
        )

        data = normalizar_texto(
            journal.get("created_on")
        )

        tipo = (
            "comentario"
            if _journal_tem_nota(journal)
            else "alteracao"
        )

        return {
            "autor": autor,
            "data": data,
            "tipo": tipo,
            "comentario": notas,
        }

    return None


# ============================================================
# ANALISAR CHAMADO INDIVIDUAL
# ============================================================

def analisar_chamado_primeiro_combate(
    chamado_id: int,
) -> dict:
    """
    Consulta um chamado individualmente no Redmine,
    incluindo journals, e determina se já houve atuação.

    Esta função é SOMENTE LEITURA.
    """

    resultado = {
        "id": chamado_id,
        "teve_atuacao": False,
        "primeira_atuacao": None,
        "situacao_ednna": "AGUARDANDO_PRIMEIRO_COMBATE",
        "erro": "",
    }

    try:

        chamado = buscar_detalhes_chamado(
            chamado_id,
            incluir_journals=True,
        )

        journals = (
            chamado.get("journals")
            or []
        )

        primeira_atuacao = (
            localizar_primeira_atuacao(
                journals
            )
        )

        if primeira_atuacao:

            resultado["teve_atuacao"] = True

            resultado["primeira_atuacao"] = (
                primeira_atuacao
            )

            resultado["situacao_ednna"] = (
                "JA_ATUADO"
            )

        return resultado

    except Exception as exc:

        resultado["situacao_ednna"] = (
            "ERRO_ANALISE"
        )

        resultado["erro"] = str(exc)

        return resultado


# ============================================================
# EXTRAIR IDs DO DATAFRAME
# ============================================================

def _extrair_ids_chamados(
    frame: pd.DataFrame,
) -> list[int]:
    """
    Obtém os IDs dos chamados a partir da coluna '#'.
    """

    if frame is None or frame.empty:
        return []

    if "#" not in frame.columns:
        return []

    ids = []

    for valor in frame["#"].tolist():

        try:

            chamado_id = int(valor)

            if chamado_id > 0:
                ids.append(chamado_id)

        except (ValueError, TypeError):
            continue

    return list(dict.fromkeys(ids))


# ============================================================
# ANALISAR FILA COMPLETA
# ============================================================

def analisar_fila_primeiro_combate(
    frame: pd.DataFrame,
    max_workers: int | None = None,
) -> pd.DataFrame:
    """
    Analisa os journals dos chamados atualmente em estado Aberto.

    Fluxo:

    DataFrame do dashboard
            ↓
    Estado = Aberto
            ↓
    IDs dos chamados
            ↓
    GET issue/:id?include=journals
            ↓
    classificação:
        AGUARDANDO_PRIMEIRO_COMBATE
        JA_ATUADO
        ERRO_ANALISE

    IMPORTANTE:

    - não altera Redmine;
    - não envia e-mail;
    - não muda status;
    - não executa scripts.
    """

    fila = filtrar_estado_aberto_dataframe(
        frame
    )

    if fila.empty:
        return fila.copy()

    ids = _extrair_ids_chamados(
        fila
    )

    if not ids:
        return fila.copy()

    workers = (
        max_workers
        if max_workers is not None
        else MAX_WORKERS
    )

    workers = max(
        1,
        int(workers),
    )

    resultados = {}

    # --------------------------------------------------------
    # CONSULTA CONTROLADA
    # --------------------------------------------------------
    #
    # Mantemos poucos workers porque já observamos que
    # o Redmine pode apresentar lentidão/ConnectTimeout.
    # --------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futuros = {
            executor.submit(
                analisar_chamado_primeiro_combate,
                chamado_id,
            ): chamado_id
            for chamado_id in ids
        }

        for futuro in as_completed(futuros):

            chamado_id = futuros[futuro]

            try:
                resultados[chamado_id] = (
                    futuro.result()
                )

            except Exception as exc:

                resultados[chamado_id] = {
                    "id": chamado_id,
                    "teve_atuacao": False,
                    "primeira_atuacao": None,
                    "situacao_ednna": (
                        "ERRO_ANALISE"
                    ),
                    "erro": str(exc),
                }

    # --------------------------------------------------------
    # ADICIONAR RESULTADOS AO DATAFRAME
    # --------------------------------------------------------

    resultado_frame = fila.copy()

    resultado_frame[
        "EDNNA - Situação"
    ] = resultado_frame["#"].map(
        lambda x: (
            resultados
            .get(
                int(x),
                {},
            )
            .get(
                "situacao_ednna",
                "ERRO_ANALISE",
            )
        )
    )

    resultado_frame[
        "EDNNA - Teve atuação"
    ] = resultado_frame["#"].map(
        lambda x: (
            resultados
            .get(
                int(x),
                {},
            )
            .get(
                "teve_atuacao",
                False,
            )
        )
    )

    resultado_frame[
        "EDNNA - Autor primeira atuação"
    ] = resultado_frame["#"].map(
        lambda x: (
            (
                resultados
                .get(
                    int(x),
                    {},
                )
                .get(
                    "primeira_atuacao",
                )
                or {}
            )
            .get(
                "autor",
                "",
            )
        )
    )

    resultado_frame[
        "EDNNA - Data primeira atuação"
    ] = resultado_frame["#"].map(
        lambda x: (
            (
                resultados
                .get(
                    int(x),
                    {},
                )
                .get(
                    "primeira_atuacao",
                )
                or {}
            )
            .get(
                "data",
                "",
            )
        )
    )

    resultado_frame[
        "EDNNA - Tipo primeira atuação"
    ] = resultado_frame["#"].map(
        lambda x: (
            (
                resultados
                .get(
                    int(x),
                    {},
                )
                .get(
                    "primeira_atuacao",
                )
                or {}
            )
            .get(
                "tipo",
                "",
            )
        )
    )

    resultado_frame[
        "EDNNA - Erro"
    ] = resultado_frame["#"].map(
        lambda x: (
            resultados
            .get(
                int(x),
                {},
            )
            .get(
                "erro",
                "",
            )
        )
    )

    return resultado_frame


# ============================================================
# FILTRAR SOMENTE OS QUE PRECISAM DE PRIMEIRO COMBATE
# ============================================================

def filtrar_aguardando_primeiro_combate(
    frame_analisado: pd.DataFrame,
) -> pd.DataFrame:
    """
    Depois da análise dos journals, retorna somente chamados
    que ainda não tiveram primeiro combate.
    """

    if frame_analisado is None:
        return pd.DataFrame()

    if frame_analisado.empty:
        return frame_analisado.copy()

    coluna = "EDNNA - Situação"

    if coluna not in frame_analisado.columns:
        return frame_analisado.iloc[0:0].copy()

    return frame_analisado[
        frame_analisado[coluna]
        == "AGUARDANDO_PRIMEIRO_COMBATE"
    ].copy()


# ============================================================
# RESUMO DA ANÁLISE
# ============================================================

def resumo_analise_primeiro_combate(
    frame_analisado: pd.DataFrame,
) -> dict:
    """
    Gera os indicadores finais da análise de journals.
    """

    if (
        frame_analisado is None
        or frame_analisado.empty
        or "EDNNA - Situação"
        not in frame_analisado.columns
    ):
        return {
            "analisados": 0,
            "aguardando_primeiro_combate": 0,
            "ja_atuados": 0,
            "erros": 0,
        }

    situacoes = (
        frame_analisado[
            "EDNNA - Situação"
        ]
        .fillna("")
        .astype(str)
    )

    return {
        "analisados": len(
            frame_analisado
        ),

        "aguardando_primeiro_combate": int(
            (
                situacoes
                == "AGUARDANDO_PRIMEIRO_COMBATE"
            ).sum()
        ),

        "ja_atuados": int(
            (
                situacoes
                == "JA_ATUADO"
            ).sum()
        ),

        "erros": int(
            (
                situacoes
                == "ERRO_ANALISE"
            ).sum()
        ),
    }
