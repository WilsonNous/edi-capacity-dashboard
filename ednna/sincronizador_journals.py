from __future__ import annotations

import os
from time import sleep
from typing import Any, Callable

import pandas as pd

from redmine_api import buscar_detalhes_chamado
from ednna.armazenamento import (
    agora_brasil_iso,
    obter_analise_primeiro_combate,
    salvar_analise_primeiro_combate,
    salvar_journals,
    salvar_metadado,
)
from ednna.primeiro_combate import (
    autores_edi_do_dataframe,
    classificar_journals_primeiro_combate,
    filtrar_estado_aberto_dataframe,
)
from ednna.sincronizador import normalizar_marca_alteracao

BATCH_SIZE = max(
    1,
    int(os.getenv("EDNNA_SYNC_BATCH_SIZE", "5")),
)

INTERVALO_SEGUNDOS = max(
    0.0,
    float(os.getenv("EDNNA_SYNC_INTERVAL_SECONDS", "0.10")),
)

MAX_ERROS_CONSECUTIVOS = max(
    1,
    int(os.getenv("EDNNA_MAX_ERROS_CONSECUTIVOS", "3")),
)


def _inteiro(valor: Any) -> int | None:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
    except Exception:
        pass
    return str(valor).strip()


def chamado_precisa_analise(
    chamado_id: int,
    alterado_em: str,
) -> bool:
    analise = obter_analise_primeiro_combate(chamado_id)

    if analise is None:
        return True

    return (
        normalizar_marca_alteracao(
            analise.get("alterado_em_redmine")
        )
        != normalizar_marca_alteracao(
            alterado_em
        )
    )


def listar_pendentes_dataframe(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    candidatos = filtrar_estado_aberto_dataframe(
        frame
    )

    if candidatos.empty:
        return candidatos

    indices = []

    for indice, row in candidatos.iterrows():
        chamado_id = _inteiro(
            row.get("#")
        )

        if chamado_id is None:
            continue

        if chamado_precisa_analise(
            chamado_id,
            _texto(row.get("Alterado")),
        ):
            indices.append(indice)

    if not indices:
        return candidatos.iloc[0:0].copy()

    resultado = candidatos.loc[
        indices
    ].copy()

    colunas = []
    ascending = []

    if "Prioridade crítica" in resultado.columns:
        colunas.append(
            "Prioridade crítica"
        )
        ascending.append(False)

    if "Tempo em aberto (dias)" in resultado.columns:
        colunas.append(
            "Tempo em aberto (dias)"
        )
        ascending.append(False)

    if colunas:
        resultado = resultado.sort_values(
            colunas,
            ascending=ascending,
        )

    return resultado


def processar_chamado(
    row: pd.Series,
    autores_edi: set[str],
) -> dict:
    chamado_id = _inteiro(
        row.get("#")
    )

    if chamado_id is None:
        return {
            "ok": False,
            "id": None,
            "journals": 0,
            "situacao": "ERRO_ANALISE",
            "erro": "ID inválido.",
        }

    alterado_em = normalizar_marca_alteracao(
        row.get("Alterado")
    )

    solicitante = _texto(
        row.get("Autor")
    )

    try:
        print(
            "[EDNNA] Journals | "
            f"chamado={chamado_id} | "
            "consultando Redmine",
            flush=True,
        )

        detalhe = buscar_detalhes_chamado(
            chamado_id,
            incluir_journals=True,
        )

        journals = (
            detalhe.get("journals")
            or []
        )

        quantidade = salvar_journals(
            chamado_id,
            journals,
        )

        classificacao = (
            classificar_journals_primeiro_combate(
                journals,
                autores_edi=autores_edi,
                solicitante=solicitante,
            )
        )

        situacao = classificacao[
            "situacao"
        ]

        salvar_analise_primeiro_combate(
            chamado_id=chamado_id,
            alterado_em_redmine=alterado_em,
            situacao=situacao,
            teve_atuacao=classificacao.get(
                "teve_atuacao",
                False,
            ),
            autor_primeira_atuacao=classificacao.get(
                "autor",
                "",
            ),
            data_primeira_atuacao=classificacao.get(
                "data",
                "",
            ),
            tipo_primeira_atuacao=classificacao.get(
                "tipo",
                "",
            ),
            erro=classificacao.get(
                "erro",
                "",
            ),
        )

        print(
            "[EDNNA] Journals OK | "
            f"chamado={chamado_id} | "
            f"journals={quantidade} | "
            f"situacao={situacao}",
            flush=True,
        )

        return {
            "ok": True,
            "id": chamado_id,
            "journals": quantidade,
            **classificacao,
        }

    except Exception as exc:
        erro = str(exc)

        print(
            "[EDNNA] Journals ERRO | "
            f"chamado={chamado_id} | "
            f"erro={erro}",
            flush=True,
        )

        return {
            "ok": False,
            "id": chamado_id,
            "journals": 0,
            "situacao": "ERRO_ANALISE",
            "erro": erro,
        }


def _processar_lote(
    frame: pd.DataFrame,
    lote: pd.DataFrame,
    progresso_callback: Callable[[dict], None] | None = None,
) -> dict:
    autores_edi = autores_edi_do_dataframe(
        frame
    )

    resultado = {
        "pendentes_antes":
            len(
                listar_pendentes_dataframe(
                    frame
                )
            ),
        "selecionados":
            len(lote),
        "processados":
            0,
        "sucesso":
            0,
        "erros":
            0,
        "journals":
            0,
        "ja_atuados":
            0,
        "aguardando":
            0,
        "revisao":
            0,
        "interrompido":
            False,
        "resultados":
            [],
    }

    erros_consecutivos = 0

    for _, row in lote.iterrows():
        item = processar_chamado(
            row,
            autores_edi,
        )

        resultado["processados"] += 1

        if item.get("ok"):
            resultado["sucesso"] += 1
            erros_consecutivos = 0
        else:
            resultado["erros"] += 1
            erros_consecutivos += 1

        situacao = item.get(
            "situacao"
        )

        if situacao == "JA_ATUADO":
            resultado["ja_atuados"] += 1
        elif situacao == "AGUARDANDO_PRIMEIRO_COMBATE":
            resultado["aguardando"] += 1
        elif situacao == "REVISAO_NECESSARIA":
            resultado["revisao"] += 1

        resultado["journals"] += int(
            item.get(
                "journals",
                0,
            )
            or 0
        )

        resultado["resultados"].append(
            item
        )

        if progresso_callback:
            progresso_callback(
                {
                    **resultado,
                    "atual_id":
                        item.get("id"),
                    "atual_situacao":
                        item.get("situacao"),
                }
            )

        if erros_consecutivos >= MAX_ERROS_CONSECUTIVOS:
            resultado["interrompido"] = True

            print(
                "[EDNNA] Fila interrompida | "
                f"{erros_consecutivos} erros consecutivos",
                flush=True,
            )
            break

        if INTERVALO_SEGUNDOS > 0:
            sleep(
                INTERVALO_SEGUNDOS
            )

    resultado["pendentes_depois"] = len(
        listar_pendentes_dataframe(
            frame
        )
    )

    salvar_metadado(
        "ultima_sincronizacao_journals",
        agora_brasil_iso(),
    )

    return resultado


def sincronizar_proximo_lote(
    frame: pd.DataFrame,
    limite: int | None = None,
) -> dict:
    limite = (
        BATCH_SIZE
        if limite is None
        else max(
            1,
            int(limite),
        )
    )

    pendentes = (
        listar_pendentes_dataframe(
            frame
        )
    )

    return _processar_lote(
        frame,
        pendentes.head(
            limite
        ),
    )


def sincronizar_fila_completa(
    frame: pd.DataFrame,
    progresso_callback: Callable[[dict], None] | None = None,
) -> dict:
    """
    Processa todos os chamados que precisam de análise.

    Continua sendo sequencial. Não dispara múltiplas chamadas
    simultâneas contra o Redmine.

    A fila é interrompida automaticamente se ocorrerem
    erros consecutivos acima do limite configurado.
    """
    pendentes = (
        listar_pendentes_dataframe(
            frame
        )
    )

    return _processar_lote(
        frame,
        pendentes,
        progresso_callback=progresso_callback,
    )
