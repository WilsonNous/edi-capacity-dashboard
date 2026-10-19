"""Controlled Redmine DataFrame -> MySQL snapshots, without SQLite or external actions.

This is opt-in and intentionally not wired to dashboard startup or workers.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from ednna.mysql_snapshot_repository import carregar_snapshot, salvar_snapshot
from ednna.sincronizador import normalizar_marca_alteracao
from ednna.armazenamento import agora_brasil_iso


FIELDS = {
    "cliente": "Clientes",
    "origem": "Origem",
    "responsavel": "Atribuído a",
    "projeto": "Projeto",
    "tipo": "Tipo",
    "estado": "Estado",
    "prioridade": "Prioridade",
    "assunto": "Assunto",
    "criado_em": "Criado",
    "alterado_em": "Alterado",
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _id(value: Any) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        number = int(value)
        return number if number > 0 and str(number) == _clean(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def sincronizar_dataframe_mysql(frame: pd.DataFrame, *, limite: int = 50) -> dict:
    """Upsert up to limite Redmine rows; never read or write legacy SQLite.

    Caller must provide already retrieved Redmine data and explicitly opt in.
    A failure is counted and does not trigger any operational action.
    """
    if not isinstance(frame, pd.DataFrame) or "#" not in frame.columns:
        raise ValueError("DataFrame Redmine com coluna # obrigatorio")
    if not 1 <= limite <= 500:
        raise ValueError("limite deve estar entre 1 e 500")
    result = {"recebidos": min(len(frame), limite), "gravados": 0, "ignorados": 0, "erros": 0, "ids_erro": []}
    for _, linha in frame.head(limite).iterrows():
        dados = linha.to_dict()
        chamado_id = _id(dados.get("#"))
        if chamado_id is None:
            result["ignorados"] += 1
            continue
        snapshot = {"id": chamado_id, "sincronizado_em": agora_brasil_iso()}
        snapshot.update({key: _clean(dados.get(source)) for key, source in FIELDS.items()})
        snapshot["tempo_aberto_dias"] = _float(dados.get("Tempo em aberto (dias)"))
        snapshot["payload_json"] = dados
        snapshot["alterado_em"] = normalizar_marca_alteracao(dados.get("Alterado"))
        try:
            salvar_snapshot(snapshot)
            result["gravados"] += 1
        except Exception:
            result["erros"] += 1
            result["ids_erro"].append(chamado_id)
    return result


def verificar_chamado_mysql(chamado_id: int) -> dict | None:
    """Read-only verification of the saved snapshot and journal count."""
    snapshot = carregar_snapshot(chamado_id)
    if snapshot is None:
        return None
    chamado = snapshot["chamado"]
    return {
        "id": chamado["id"],
        "alterado_em": chamado["alterado_em"],
        "estado": chamado["estado"],
        "journals": len(snapshot["journals"]),
        "payload_presente": bool(chamado["payload_json"]),
    }
