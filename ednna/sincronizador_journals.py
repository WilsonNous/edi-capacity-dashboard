from __future__ import annotations

import os
from typing import Any

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
    filtrar_estado_aberto_dataframe,
    localizar_primeira_atuacao,
)

BATCH_SIZE = max(1, int(os.getenv("EDNNA_SYNC_BATCH_SIZE", "5")))


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


def chamado_precisa_analise(chamado_id: int, alterado_em: str) -> bool:
    analise = obter_analise_primeiro_combate(chamado_id)
    if analise is None:
        return True
    return _texto(analise.get("alterado_em_redmine")) != _texto(alterado_em)


def listar_pendentes_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    candidatos = filtrar_estado_aberto_dataframe(frame)
    if candidatos.empty:
        return candidatos

    indices = []

    for indice, row in candidatos.iterrows():
        chamado_id = _inteiro(row.get("#"))
        if chamado_id is None:
            continue

        if chamado_precisa_analise(
            chamado_id,
            _texto(row.get("Alterado")),
        ):
            indices.append(indice)

    if not indices:
        return candidatos.iloc[0:0].copy()

    resultado = candidatos.loc[indices].copy()

    colunas = []
    ascending = []

    if "Prioridade crítica" in resultado.columns:
        colunas.append("Prioridade crítica")
        ascending.append(False)

    if "Tempo em aberto (dias)" in resultado.columns:
        colunas.append("Tempo em aberto (dias)")
        ascending.append(False)

    if colunas:
        resultado = resultado.sort_values(
            colunas,
            ascending=ascending,
        )

    return resultado


def processar_chamado(row: pd.Series) -> dict:
    chamado_id = _inteiro(row.get("#"))

    if chamado_id is None:
        return {
            "ok": False,
            "id": None,
            "journals": 0,
            "situacao": "ERRO_ANALISE",
            "erro": "ID inválido.",
        }

    alterado_em = _texto(row.get("Alterado"))

    try:
        print(
            f"[EDNNA] Journals | chamado={chamado_id} | consultando Redmine",
            flush=True,
        )

        detalhe = buscar_detalhes_chamado(
            chamado_id,
            incluir_journals=True,
        )

        journals = detalhe.get("journals") or []
        quantidade = salvar_journals(chamado_id, journals)
        primeira = localizar_primeira_atuacao(journals)

        if primeira:
            situacao = "JA_ATUADO"
            teve_atuacao = True
            autor = primeira.get("autor", "")
            data = primeira.get("data", "")
            tipo = primeira.get("tipo", "")
        else:
            situacao = "AGUARDANDO_PRIMEIRO_COMBATE"
            teve_atuacao = False
            autor = ""
            data = ""
            tipo = ""

        salvar_analise_primeiro_combate(
            chamado_id=chamado_id,
            alterado_em_redmine=alterado_em,
            situacao=situacao,
            teve_atuacao=teve_atuacao,
            autor_primeira_atuacao=autor,
            data_primeira_atuacao=data,
            tipo_primeira_atuacao=tipo,
            erro="",
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
            "situacao": situacao,
            "autor": autor,
            "data": data,
            "tipo": tipo,
            "erro": "",
        }

    except Exception as exc:
        erro = str(exc)

        print(
            f"[EDNNA] Journals ERRO | chamado={chamado_id} | erro={erro}",
            flush=True,
        )

        # Importante: não sobrescrevemos uma análise anterior válida
        # quando a consulta atual ao Redmine falha.
        return {
            "ok": False,
            "id": chamado_id,
            "journals": 0,
            "situacao": "ERRO_ANALISE",
            "erro": erro,
        }


def sincronizar_proximo_lote(
    frame: pd.DataFrame,
    limite: int | None = None,
) -> dict:
    limite = BATCH_SIZE if limite is None else max(1, int(limite))

    pendentes = listar_pendentes_dataframe(frame)
    lote = pendentes.head(limite)

    resultado = {
        "pendentes_antes": len(pendentes),
        "selecionados": len(lote),
        "processados": 0,
        "sucesso": 0,
        "erros": 0,
        "journals": 0,
        "pendentes_depois": len(pendentes),
        "resultados": [],
    }

    for _, row in lote.iterrows():
        item = processar_chamado(row)
        resultado["processados"] += 1

        if item.get("ok"):
            resultado["sucesso"] += 1
        else:
            resultado["erros"] += 1

        resultado["journals"] += int(item.get("journals", 0) or 0)
        resultado["resultados"].append(item)

    resultado["pendentes_depois"] = len(
        listar_pendentes_dataframe(frame)
    )

    salvar_metadado(
        "ultima_sincronizacao_journals",
        agora_brasil_iso(),
    )

    return resultado
