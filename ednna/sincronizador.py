from __future__ import annotations

from typing import Any

import pandas as pd

from ednna.armazenamento import (
    obter_alterado_em,
    salvar_chamado,
    salvar_metadado,
    agora_brasil_iso,
)


# ============================================================
# EDNNA — INTELIGÊNCIA OPERACIONAL EDI
# Módulo: Sincronizador
# ============================================================


def _inteiro_seguro(
    valor: Any,
) -> int | None:
    """
    Converte IDs vindos do DataFrame em inteiro.
    """

    try:
        valor_int = int(valor)

        if valor_int <= 0:
            return None

        return valor_int

    except (TypeError, ValueError):
        return None


def _texto(valor: Any) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    return str(valor).strip()


# ============================================================
# SINCRONIZAÇÃO DO SNAPSHOT
# ============================================================

def sincronizar_dataframe(
    frame: pd.DataFrame,
) -> dict:
    """
    Salva no SQLite o snapshot que já foi carregado
    pelo dashboard.

    IMPORTANTE:

    Esta função NÃO consulta o Redmine.

    Ela apenas utiliza dados que o dashboard já possui.

    Retorna estatísticas da sincronização.
    """

    resultado = {
        "recebidos": 0,
        "novos": 0,
        "alterados": 0,
        "sem_alteracao": 0,
        "ignorados": 0,
        "erros": 0,
    }

    if frame is None:
        return resultado

    if not isinstance(frame, pd.DataFrame):
        return resultado

    if frame.empty:
        return resultado

    if "#" not in frame.columns:
        return resultado

    resultado["recebidos"] = len(frame)

    for _, linha in frame.iterrows():

        chamado_id = _inteiro_seguro(
            linha.get("#")
        )

        if chamado_id is None:
            resultado["ignorados"] += 1
            continue

        try:

            dados = linha.to_dict()

            alterado_atual = _texto(
                dados.get("Alterado")
            )

            alterado_cache = obter_alterado_em(
                chamado_id
            )

            # ------------------------------------------------
            # CHAMADO NOVO
            # ------------------------------------------------

            if not alterado_cache:

                salvar_chamado(
                    chamado_id,
                    dados,
                )

                resultado["novos"] += 1

                continue

            # ------------------------------------------------
            # CHAMADO ALTERADO
            # ------------------------------------------------

            if alterado_atual != alterado_cache:

                salvar_chamado(
                    chamado_id,
                    dados,
                )

                resultado["alterados"] += 1

                continue

            # ------------------------------------------------
            # SEM ALTERAÇÃO
            # ------------------------------------------------

            resultado[
                "sem_alteracao"
            ] += 1

        except Exception as exc:

            resultado["erros"] += 1

            print(
                f"[EDNNA] Erro sincronizando chamado "
                f"#{chamado_id}: {exc}"
            )

    salvar_metadado(
        "ultima_sincronizacao_snapshot",
        agora_brasil_iso(),
    )

    return resultado
