from __future__ import annotations

import pandas as pd


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
    O Redmine usa status_id='open' para representar todos os chamados
    que ainda não estão fechados. Para a EDNNA, entretanto, queremos
    inicialmente apenas o estado operacional chamado 'Aberto'.
    """
    return normalizar_texto(valor).casefold() == STATUS_PRIMEIRO_COMBATE.casefold()


def filtrar_estado_aberto_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra o DataFrame já carregado pelo dashboard e retorna apenas
    chamados cujo campo Estado seja exatamente 'Aberto'.

    Esta função:
    - não consulta o Redmine;
    - não altera chamados;
    - não executa automações;
    - apenas identifica a fila inicial de primeiro combate.
    """
    if frame is None or frame.empty:
        return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()

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


def resumo_fila_primeiro_combate(frame: pd.DataFrame) -> dict:
    """
    Gera métricas simples da fila EDNNA.

    O dashboard pode usar este retorno futuramente para reduzir
    duplicação de regras na camada visual.
    """
    fila = filtrar_estado_aberto_dataframe(frame)

    total = len(fila)

    mais_1_dia = (
        int((fila["Tempo em aberto (dias)"] >= 1).sum())
        if "Tempo em aberto (dias)" in fila.columns
        else 0
    )

    criticos = (
        int(fila["Prioridade crítica"].sum())
        if "Prioridade crítica" in fila.columns
        else 0
    )

    sem_responsavel = (
        int(
            fila["Atribuído a"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )
        if "Atribuído a" in fila.columns
        else 0
    )

    return {
        "total_estado_aberto": total,
        "ha_1_dia_ou_mais": mais_1_dia,
        "prioridade_critica": criticos,
        "sem_responsavel": sem_responsavel,
    }
