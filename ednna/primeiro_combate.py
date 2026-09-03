from __future__ import annotations

import pandas as pd


# ============================================================
# EDNNA — INTELIGÊNCIA OPERACIONAL EDI
# Módulo: Primeiro Combate
# ============================================================

STATUS_PRIMEIRO_COMBATE = "Aberto"


def normalizar_texto(valor) -> str:
    """
    Converte qualquer valor simples em texto limpo.
    """
    if valor is None:
        return ""

    return str(valor).strip()


def eh_estado_aberto(valor) -> bool:
    """
    Retorna True somente quando o nome real do estado é 'Aberto'.

    Importante:
    No Redmine, status_id='open' representa todos os chamados
    que ainda não estão fechados.

    Para o primeiro combate da EDNNA queremos, nesta etapa,
    somente os chamados cujo Estado real seja 'Aberto'.
    """
    return (
        normalizar_texto(valor).casefold()
        == STATUS_PRIMEIRO_COMBATE.casefold()
    )


def filtrar_estado_aberto_dataframe(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recebe o DataFrame que já foi carregado pelo dashboard
    e retorna somente os chamados cujo Estado seja 'Aberto'.

    IMPORTANTE:

    Esta função NÃO:
    - consulta novamente o Redmine;
    - altera chamados;
    - envia e-mails;
    - muda status;
    - executa automações.

    Ela apenas identifica a fila inicial de primeiro combate.
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


def resumo_fila_primeiro_combate(
    frame: pd.DataFrame,
) -> dict:
    """
    Gera um resumo simples da fila inicial da EDNNA.

    Retorna:
    - total de chamados em estado Aberto;
    - chamados com 1 dia ou mais;
    - chamados com prioridade crítica;
    - chamados sem responsável.
    """

    fila = filtrar_estado_aberto_dataframe(frame)

    total = len(fila)

    # --------------------------------------------------------
    # CHAMADOS COM 1 DIA OU MAIS
    # --------------------------------------------------------

    if "Tempo em aberto (dias)" in fila.columns:
        mais_1_dia = int(
            (
                fila["Tempo em aberto (dias)"] >= 1
            ).sum()
        )
    else:
        mais_1_dia = 0

    # --------------------------------------------------------
    # PRIORIDADE CRÍTICA
    # --------------------------------------------------------

    if "Prioridade crítica" in fila.columns:
        criticos = int(
            fila["Prioridade crítica"]
            .fillna(False)
            .astype(bool)
            .sum()
        )
    else:
        criticos = 0

    # --------------------------------------------------------
    # SEM RESPONSÁVEL
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # RETORNO
    # --------------------------------------------------------

    return {
        "total_estado_aberto": total,
        "ha_1_dia_ou_mais": mais_1_dia,
        "prioridade_critica": criticos,
        "sem_responsavel": sem_responsavel,
    }
