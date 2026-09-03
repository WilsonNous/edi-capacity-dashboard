from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo


# ============================================================
# EDNNA — INTELIGÊNCIA OPERACIONAL EDI
# Módulo: Armazenamento
# ============================================================

FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def agora_brasil_iso() -> str:
    """
    Retorna data/hora atual de São Paulo em ISO 8601.
    """
    return datetime.now(FUSO_BRASIL).isoformat(timespec="seconds")


# ============================================================
# CAMINHO DO BANCO
# ============================================================
#
# Azure App Service Linux:
# somente /home é persistente.
#
# Local:
# usa ./data/ednna.db
#
# Pode ser sobrescrito pela variável:
#
# EDNNA_DB_PATH=/home/data/ednna.db
# ============================================================

def obter_caminho_banco() -> Path:
    caminho_configurado = os.getenv("EDNNA_DB_PATH", "").strip()

    if caminho_configurado:
        caminho = Path(caminho_configurado)
    elif os.getenv("WEBSITE_INSTANCE_ID"):
        caminho = Path("/home/data/ednna.db")
    else:
        caminho = Path("data/ednna.db")

    caminho.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return caminho


DB_PATH = obter_caminho_banco()


# ============================================================
# CONEXÃO
# ============================================================

@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """
    Abre conexão SQLite de forma controlada.

    Para este MVP não usamos WAL.

    O App Service utiliza armazenamento persistente em /home,
    e queremos manter o modelo mais conservador possível
    enquanto trabalhamos com apenas uma instância.
    """

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    try:
        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        conn.execute(
            "PRAGMA busy_timeout = 30000"
        )

        yield conn

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# CRIAÇÃO DAS TABELAS
# ============================================================

def inicializar_banco() -> None:
    """
    Cria as tabelas da EDNNA caso ainda não existam.
    """

    with conectar() as conn:

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chamados (
                id INTEGER PRIMARY KEY,

                cliente TEXT,
                origem TEXT,
                responsavel TEXT,
                projeto TEXT,
                tipo TEXT,
                estado TEXT,
                prioridade TEXT,
                assunto TEXT,

                criado_em TEXT,
                alterado_em TEXT,

                tempo_aberto_dias REAL,

                payload_json TEXT,

                sincronizado_em TEXT NOT NULL
            );


            CREATE INDEX IF NOT EXISTS idx_chamados_estado
            ON chamados (estado);


            CREATE INDEX IF NOT EXISTS idx_chamados_alterado
            ON chamados (alterado_em);


            CREATE TABLE IF NOT EXISTS journals (
                id INTEGER PRIMARY KEY,

                chamado_id INTEGER NOT NULL,

                autor TEXT,
                criado_em TEXT,
                notas TEXT,

                detalhes_json TEXT,

                sincronizado_em TEXT NOT NULL,

                FOREIGN KEY (chamado_id)
                    REFERENCES chamados(id)
                    ON DELETE CASCADE
            );


            CREATE INDEX IF NOT EXISTS idx_journals_chamado
            ON journals (chamado_id);


            CREATE TABLE IF NOT EXISTS analises_primeiro_combate (
                chamado_id INTEGER PRIMARY KEY,

                alterado_em_redmine TEXT,

                situacao TEXT NOT NULL,
                teve_atuacao INTEGER NOT NULL DEFAULT 0,

                autor_primeira_atuacao TEXT,
                data_primeira_atuacao TEXT,
                tipo_primeira_atuacao TEXT,

                erro TEXT,

                analisado_em TEXT NOT NULL,

                FOREIGN KEY (chamado_id)
                    REFERENCES chamados(id)
                    ON DELETE CASCADE
            );


            CREATE TABLE IF NOT EXISTS metadados (
                chave TEXT PRIMARY KEY,
                valor TEXT,
                atualizado_em TEXT NOT NULL
            );
            """
        )


# ============================================================
# UTILIDADES
# ============================================================

def _texto(valor: Any) -> str:
    if valor is None:
        return ""

    try:
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
    except Exception:
        pass

    return str(valor).strip()


def _float(valor: Any) -> float | None:
    if valor is None:
        return None

    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _json_seguro(valor: Any) -> str:
    """
    Serializa estruturas Python/Pandas sem quebrar
    com datas e tipos desconhecidos.
    """

    return json.dumps(
        valor,
        ensure_ascii=False,
        default=str,
    )


# ============================================================
# CHAMADOS
# ============================================================

def salvar_chamado(
    chamado_id: int,
    dados: dict,
) -> None:
    """
    Insere ou atualiza um chamado no cache local da EDNNA.
    """

    agora = agora_brasil_iso()

    with conectar() as conn:

        conn.execute(
            """
            INSERT INTO chamados (
                id,
                cliente,
                origem,
                responsavel,
                projeto,
                tipo,
                estado,
                prioridade,
                assunto,
                criado_em,
                alterado_em,
                tempo_aberto_dias,
                payload_json,
                sincronizado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(id) DO UPDATE SET

                cliente = excluded.cliente,
                origem = excluded.origem,
                responsavel = excluded.responsavel,
                projeto = excluded.projeto,
                tipo = excluded.tipo,
                estado = excluded.estado,
                prioridade = excluded.prioridade,
                assunto = excluded.assunto,
                criado_em = excluded.criado_em,
                alterado_em = excluded.alterado_em,
                tempo_aberto_dias = excluded.tempo_aberto_dias,
                payload_json = excluded.payload_json,
                sincronizado_em = excluded.sincronizado_em
            """,
            (
                chamado_id,
                _texto(dados.get("Clientes")),
                _texto(dados.get("Origem")),
                _texto(dados.get("Atribuído a")),
                _texto(dados.get("Projeto")),
                _texto(dados.get("Tipo")),
                _texto(dados.get("Estado")),
                _texto(dados.get("Prioridade")),
                _texto(dados.get("Assunto")),
                _texto(dados.get("Criado")),
                _texto(dados.get("Alterado")),
                _float(
                    dados.get(
                        "Tempo em aberto (dias)"
                    )
                ),
                _json_seguro(dados),
                agora,
            ),
        )


def obter_chamado(
    chamado_id: int,
) -> dict | None:
    """
    Retorna um chamado armazenado.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT *
            FROM chamados
            WHERE id = ?
            """,
            (chamado_id,),
        ).fetchone()

    if linha is None:
        return None

    return dict(linha)


def listar_chamados(
    estado: str | None = None,
) -> list[dict]:
    """
    Lista os chamados existentes no cache.
    """

    with conectar() as conn:

        if estado:

            linhas = conn.execute(
                """
                SELECT *
                FROM chamados
                WHERE LOWER(TRIM(estado)) = LOWER(TRIM(?))
                ORDER BY id DESC
                """,
                (estado,),
            ).fetchall()

        else:

            linhas = conn.execute(
                """
                SELECT *
                FROM chamados
                ORDER BY id DESC
                """
            ).fetchall()

    return [
        dict(linha)
        for linha in linhas
    ]


def obter_alterado_em(
    chamado_id: int,
) -> str:
    """
    Obtém o updated_on/Alterado conhecido pela EDNNA.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT alterado_em
            FROM chamados
            WHERE id = ?
            """,
            (chamado_id,),
        ).fetchone()

    if not linha:
        return ""

    return _texto(
        linha["alterado_em"]
    )


# ============================================================
# JOURNALS
# ============================================================

def salvar_journals(
    chamado_id: int,
    journals: list[dict],
) -> int:
    """
    Armazena os journals de um chamado.

    Journals já existentes são atualizados.
    """

    agora = agora_brasil_iso()

    quantidade = 0

    with conectar() as conn:

        for journal in journals:

            journal_id = journal.get("id")

            if journal_id is None:
                continue

            usuario = (
                journal.get("user")
                or {}
            )

            autor = _texto(
                usuario.get("name")
            )

            criado_em = _texto(
                journal.get("created_on")
            )

            notas = _texto(
                journal.get("notes")
            )

            detalhes = (
                journal.get("details")
                or []
            )

            conn.execute(
                """
                INSERT INTO journals (
                    id,
                    chamado_id,
                    autor,
                    criado_em,
                    notas,
                    detalhes_json,
                    sincronizado_em
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id) DO UPDATE SET

                    chamado_id = excluded.chamado_id,
                    autor = excluded.autor,
                    criado_em = excluded.criado_em,
                    notas = excluded.notas,
                    detalhes_json = excluded.detalhes_json,
                    sincronizado_em = excluded.sincronizado_em
                """,
                (
                    int(journal_id),
                    chamado_id,
                    autor,
                    criado_em,
                    notas,
                    _json_seguro(detalhes),
                    agora,
                ),
            )

            quantidade += 1

    return quantidade


def listar_journals(
    chamado_id: int,
) -> list[dict]:
    """
    Retorna journals armazenados de um chamado.
    """

    with conectar() as conn:

        linhas = conn.execute(
            """
            SELECT *
            FROM journals
            WHERE chamado_id = ?
            ORDER BY criado_em, id
            """,
            (chamado_id,),
        ).fetchall()

    return [
        dict(linha)
        for linha in linhas
    ]


# ============================================================
# ANÁLISE DE PRIMEIRO COMBATE
# ============================================================

def salvar_analise_primeiro_combate(
    chamado_id: int,
    alterado_em_redmine: str,
    situacao: str,
    teve_atuacao: bool,
    autor_primeira_atuacao: str = "",
    data_primeira_atuacao: str = "",
    tipo_primeira_atuacao: str = "",
    erro: str = "",
) -> None:
    """
    Persiste o resultado da análise de primeiro combate.
    """

    with conectar() as conn:

        conn.execute(
            """
            INSERT INTO analises_primeiro_combate (
                chamado_id,
                alterado_em_redmine,
                situacao,
                teve_atuacao,
                autor_primeira_atuacao,
                data_primeira_atuacao,
                tipo_primeira_atuacao,
                erro,
                analisado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(chamado_id) DO UPDATE SET

                alterado_em_redmine =
                    excluded.alterado_em_redmine,

                situacao =
                    excluded.situacao,

                teve_atuacao =
                    excluded.teve_atuacao,

                autor_primeira_atuacao =
                    excluded.autor_primeira_atuacao,

                data_primeira_atuacao =
                    excluded.data_primeira_atuacao,

                tipo_primeira_atuacao =
                    excluded.tipo_primeira_atuacao,

                erro =
                    excluded.erro,

                analisado_em =
                    excluded.analisado_em
            """,
            (
                chamado_id,
                alterado_em_redmine,
                situacao,
                int(bool(teve_atuacao)),
                autor_primeira_atuacao,
                data_primeira_atuacao,
                tipo_primeira_atuacao,
                erro,
                agora_brasil_iso(),
            ),
        )


def obter_analise_primeiro_combate(
    chamado_id: int,
) -> dict | None:
    """
    Obtém a última análise conhecida de um chamado.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT *
            FROM analises_primeiro_combate
            WHERE chamado_id = ?
            """,
            (chamado_id,),
        ).fetchone()

    if linha is None:
        return None

    return dict(linha)


# ============================================================
# METADADOS
# ============================================================

def salvar_metadado(
    chave: str,
    valor: str,
) -> None:

    with conectar() as conn:

        conn.execute(
            """
            INSERT INTO metadados (
                chave,
                valor,
                atualizado_em
            )
            VALUES (?, ?, ?)

            ON CONFLICT(chave) DO UPDATE SET
                valor = excluded.valor,
                atualizado_em = excluded.atualizado_em
            """,
            (
                chave,
                valor,
                agora_brasil_iso(),
            ),
        )


def obter_metadado(
    chave: str,
) -> str:
    """
    Retorna um metadado da EDNNA.
    """

    with conectar() as conn:

        linha = conn.execute(
            """
            SELECT valor
            FROM metadados
            WHERE chave = ?
            """,
            (chave,),
        ).fetchone()

    if linha is None:
        return ""

    return _texto(
        linha["valor"]
    )


# ============================================================
# DIAGNÓSTICO
# ============================================================

def obter_diagnostico_banco() -> dict:
    """
    Retorna informações básicas do banco local.
    """

    inicializar_banco()

    with conectar() as conn:

        chamados = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM chamados
            """
        ).fetchone()["total"]

        journals = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM journals
            """
        ).fetchone()["total"]

        analises = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM analises_primeiro_combate
            """
        ).fetchone()["total"]

    return {
        "arquivo": str(DB_PATH),
        "chamados": chamados,
        "journals": journals,
        "analises_primeiro_combate": analises,
    }


# ============================================================
# INICIALIZAÇÃO AUTOMÁTICA
# ============================================================

inicializar_banco()
