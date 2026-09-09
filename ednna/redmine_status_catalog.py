from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


TZ_BRASIL = ZoneInfo("America/Sao_Paulo")


def _db_path() -> Path:
    configurado = os.getenv("EDNNA_DB_PATH")

    if configurado:
        return Path(configurado)

    if Path("/home/data").exists():
        return Path("/home/data/ednna.db")

    return Path("data/ednna.db")


def _conectar() -> sqlite3.Connection:
    caminho = _db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        caminho,
        timeout=10,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _normalizar_nome(valor: str) -> str:
    return " ".join(
        str(valor or "")
        .strip()
        .casefold()
        .split()
    )


def inicializar_catalogo_status() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS redmine_status_catalog (
                status_id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                nome_normalizado TEXT NOT NULL UNIQUE,
                atualizado_em TEXT NOT NULL
            )
            """
        )


def salvar_status(status_id: int, nome: str) -> None:
    inicializar_catalogo_status()

    agora = datetime.now(
        TZ_BRASIL
    ).isoformat(
        timespec="seconds"
    )

    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO redmine_status_catalog (
                status_id,
                nome,
                nome_normalizado,
                atualizado_em
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(status_id)
            DO UPDATE SET
                nome = excluded.nome,
                nome_normalizado = excluded.nome_normalizado,
                atualizado_em = excluded.atualizado_em
            """,
            (
                int(status_id),
                str(nome),
                _normalizar_nome(nome),
                agora,
            ),
        )


def obter_status_id_cache(nome: str) -> int | None:
    inicializar_catalogo_status()

    with _conectar() as conn:
        row = conn.execute(
            """
            SELECT status_id
              FROM redmine_status_catalog
             WHERE nome_normalizado = ?
            """,
            (
                _normalizar_nome(nome),
            ),
        ).fetchone()

    if row is None:
        return None

    return int(
        row["status_id"]
    )


def listar_status_cache() -> list[dict]:
    inicializar_catalogo_status()

    with _conectar() as conn:
        rows = conn.execute(
            """
            SELECT status_id, nome, atualizado_em
              FROM redmine_status_catalog
             ORDER BY status_id
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def sincronizar_catalogo_status(
    *,
    redmine_url: str,
    headers: dict[str, str],
) -> list[dict]:
    resposta = requests.get(
        f"{redmine_url.rstrip('/')}/issue_statuses.json",
        headers=headers,
        timeout=(20, 40),
    )

    if resposta.status_code != 200:
        raise RuntimeError(
            "Falha ao sincronizar catálogo de status: "
            f"HTTP {resposta.status_code} - "
            f"{resposta.text[:800]}"
        )

    resultado = []

    for item in resposta.json().get(
        "issue_statuses",
        [],
    ):
        try:
            status_id = int(
                item.get("id")
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        nome = str(
            item.get("name", "")
            or ""
        ).strip()

        if not nome:
            continue

        salvar_status(
            status_id,
            nome,
        )

        resultado.append(
            {
                "status_id": status_id,
                "nome": nome,
            }
        )

    return resultado
