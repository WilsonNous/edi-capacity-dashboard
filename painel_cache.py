from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def agora_brasil_iso() -> str:
    return datetime.now(FUSO_BRASIL).isoformat(timespec="seconds")


def obter_caminho_banco() -> Path:
    configurado = os.getenv("PAINEL_DB_PATH", "").strip()
    if configurado:
        caminho = Path(configurado)
    elif os.getenv("WEBSITE_INSTANCE_ID"):
        caminho = Path("/home/data/painel.db")
    else:
        caminho = Path("data/painel.db")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


DB_PATH = obter_caminho_banco()


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_banco() -> None:
    with conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                chave TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                quantidade INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metadados (
                chave TEXT PRIMARY KEY,
                valor TEXT,
                atualizado_em TEXT NOT NULL
            );
            """
        )


def _json_seguro(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, default=str)


def _parse_data(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        data = datetime.fromisoformat(valor)
        if data.tzinfo is None:
            data = data.replace(tzinfo=FUSO_BRASIL)
        return data
    except Exception:
        return None


def idade_segundos(atualizado_em: str | None) -> float | None:
    data = _parse_data(atualizado_em)
    if data is None:
        return None
    return max(0.0, (datetime.now(FUSO_BRASIL) - data).total_seconds())


def cache_valido(atualizado_em: str | None, ttl_seconds: int) -> bool:
    idade = idade_segundos(atualizado_em)
    return idade is not None and idade < ttl_seconds


def salvar_snapshot(chave: str, payload: list[dict]) -> None:
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO snapshots (chave, payload_json, quantidade, atualizado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                payload_json = excluded.payload_json,
                quantidade = excluded.quantidade,
                atualizado_em = excluded.atualizado_em
            """,
            (chave, _json_seguro(payload), len(payload), agora),
        )


def carregar_snapshot(chave: str) -> dict | None:
    with conectar() as conn:
        linha = conn.execute(
            """
            SELECT chave, payload_json, quantidade, atualizado_em
            FROM snapshots
            WHERE chave = ?
            """,
            (chave,),
        ).fetchone()

    if linha is None:
        return None

    try:
        payload = json.loads(linha["payload_json"])
    except Exception:
        return None

    if not isinstance(payload, list):
        return None

    return {
        "chave": linha["chave"],
        "payload": payload,
        "quantidade": int(linha["quantidade"] or 0),
        "atualizado_em": linha["atualizado_em"],
        "idade_s": idade_segundos(linha["atualizado_em"]),
    }


def salvar_metadado(chave: str, valor: str) -> None:
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO metadados (chave, valor, atualizado_em)
            VALUES (?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                valor = excluded.valor,
                atualizado_em = excluded.atualizado_em
            """,
            (chave, str(valor), agora_brasil_iso()),
        )



def salvar_metadado_json(chave: str, valor: Any) -> None:
    salvar_metadado(
        chave,
        _json_seguro(valor),
    )


def obter_metadado_json(chave: str, padrao: Any = None) -> Any:
    bruto = obter_metadado(chave)
    if not bruto:
        return padrao
    try:
        return json.loads(bruto)
    except Exception:
        return padrao


def obter_metadado(chave: str) -> str:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT valor FROM metadados WHERE chave = ?",
            (chave,),
        ).fetchone()
    return str(linha["valor"]) if linha is not None else ""


def obter_diagnostico() -> dict:
    inicializar_banco()
    with conectar() as conn:
        snapshots = conn.execute(
            "SELECT COUNT(*) AS total FROM snapshots"
        ).fetchone()["total"]
        ultima = conn.execute(
            "SELECT MAX(atualizado_em) AS ultima FROM snapshots"
        ).fetchone()["ultima"]

    return {
        "arquivo": str(DB_PATH),
        "existe": DB_PATH.exists(),
        "snapshots": int(snapshots or 0),
        "ultima_atualizacao": ultima or "",
    }


inicializar_banco()
print(f"[PAINEL] SQLite inicializado | arquivo={DB_PATH}", flush=True)
