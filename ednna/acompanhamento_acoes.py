from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


TZ_BRASIL = ZoneInfo("America/Sao_Paulo")


def _db_path() -> Path:
    configurado = os.getenv("EDNNA_DB_PATH")

    if configurado:
        return Path(configurado)

    if Path("/home/data").exists():
        return Path("/home/data/ednna.db")

    return Path("data/ednna.db")


def _agora() -> datetime:
    return datetime.now(TZ_BRASIL)


def _iso(valor: datetime) -> str:
    return valor.isoformat(timespec="seconds")


def _conectar() -> sqlite3.Connection:
    caminho = _db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        caminho,
        timeout=10,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def inicializar_acompanhamento() -> None:
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acoes_operacionais (
                chamado_id INTEGER NOT NULL,
                regra_id TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'RASCUNHO',
                enviado_em TEXT,
                prazo_resposta_em TEXT,
                resposta_recebida_em TEXT,
                atualizado_em TEXT NOT NULL,
                observacao TEXT,
                erro_envio TEXT,
                redmine_atualizado_em TEXT,
                redmine_erro TEXT,
                redmine_status_nome TEXT,
                redmine_status_atualizado_em TEXT,
                email_assunto TEXT,
                graph_message_id TEXT,
                graph_conversation_id TEXT,
                graph_internet_message_id TEXT,
                resposta_graph_message_id TEXT,
                resposta_remetente TEXT,
                resposta_assunto TEXT,
                resposta_corpo TEXT,
                monitorado_em TEXT,
                PRIMARY KEY (chamado_id, regra_id)
            )
            """
        )

        colunas = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(acoes_operacionais)"
            ).fetchall()
        }

        if "erro_envio" not in colunas:
            conn.execute(
                """
                ALTER TABLE acoes_operacionais
                ADD COLUMN erro_envio TEXT
                """
            )


        if "redmine_atualizado_em" not in colunas:
            conn.execute(
                """
                ALTER TABLE acoes_operacionais
                ADD COLUMN redmine_atualizado_em TEXT
                """
            )

        if "redmine_erro" not in colunas:
            conn.execute(
                """
                ALTER TABLE acoes_operacionais
                ADD COLUMN redmine_erro TEXT
                """
            )


        if "redmine_status_nome" not in colunas:
            conn.execute(
                """
                ALTER TABLE acoes_operacionais
                ADD COLUMN redmine_status_nome TEXT
                """
            )

        if "redmine_status_atualizado_em" not in colunas:
            conn.execute(
                """
                ALTER TABLE acoes_operacionais
                ADD COLUMN redmine_status_atualizado_em TEXT
                """
            )

        novas_colunas = {
            "email_assunto": "TEXT",
            "graph_message_id": "TEXT",
            "graph_conversation_id": "TEXT",
            "graph_internet_message_id": "TEXT",
            "resposta_graph_message_id": "TEXT",
            "resposta_remetente": "TEXT",
            "resposta_assunto": "TEXT",
            "resposta_corpo": "TEXT",
            "monitorado_em": "TEXT",
            "responsavel_anterior_id": "INTEGER",
            "responsavel_anterior_nome": "TEXT",
            "ednna_assumiu_em": "TEXT",
        }

        for nome, tipo in novas_colunas.items():
            if nome not in colunas:
                conn.execute(
                    f"ALTER TABLE acoes_operacionais ADD COLUMN {nome} {tipo}"
                )


def _adicionar_dias_uteis(
    inicio: datetime,
    dias: int,
) -> datetime:
    atual = inicio
    adicionados = 0

    while adicionados < max(dias, 0):
        atual += timedelta(days=1)

        if atual.weekday() < 5:
            adicionados += 1

    return atual


def obter_acompanhamento(
    chamado_id: int,
    regra_id: str,
) -> dict:
    inicializar_acompanhamento()

    with _conectar() as conn:
        row = conn.execute(
            """
            SELECT *
              FROM acoes_operacionais
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (int(chamado_id), str(regra_id)),
        ).fetchone()

    if row is None:
        return {
            "chamado_id": int(chamado_id),
            "regra_id": str(regra_id),
            "estado": "RASCUNHO",
            "enviado_em": "",
            "prazo_resposta_em": "",
            "resposta_recebida_em": "",
            "observacao": "",
            "erro_envio": "",
            "redmine_atualizado_em": "",
            "redmine_erro": "",
            "redmine_status_nome": "",
            "redmine_status_atualizado_em": "",
            "email_assunto": "",
            "graph_message_id": "",
            "graph_conversation_id": "",
            "graph_internet_message_id": "",
            "resposta_graph_message_id": "",
            "resposta_remetente": "",
            "resposta_assunto": "",
            "resposta_corpo": "",
            "monitorado_em": "",
        }

    dados = dict(row)

    if (
        dados.get("estado") == "AGUARDANDO_RESPOSTA"
        and dados.get("prazo_resposta_em")
    ):
        try:
            if _agora() > datetime.fromisoformat(
                dados["prazo_resposta_em"]
            ):
                dados["estado"] = "PRAZO_VENCIDO"
        except Exception:
            pass

    return dados


def adquirir_envio(
    chamado_id: int,
    regra_id: str,
) -> tuple[bool, dict]:
    inicializar_acompanhamento()

    conn = _conectar()

    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT *
              FROM acoes_operacionais
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (int(chamado_id), str(regra_id)),
        ).fetchone()

        if row is not None:
            estado = str(row["estado"] or "")

            if estado in {
                "ENVIANDO",
                "AGUARDANDO_RESPOSTA",
                "PRAZO_VENCIDO",
                "RESPOSTA_RECEBIDA",
            }:
                conn.execute("ROLLBACK")
                return False, dict(row)

        agora = _iso(_agora())

        conn.execute(
            """
            INSERT INTO acoes_operacionais (
                chamado_id,
                regra_id,
                estado,
                atualizado_em,
                erro_envio
            )
            VALUES (?, ?, 'ENVIANDO', ?, NULL)
            ON CONFLICT(chamado_id, regra_id)
            DO UPDATE SET
                estado = 'ENVIANDO',
                atualizado_em = excluded.atualizado_em,
                erro_envio = NULL
            """,
            (int(chamado_id), str(regra_id), agora),
        )

        conn.execute("COMMIT")

        return True, obter_acompanhamento(
            chamado_id,
            regra_id,
        )

    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def confirmar_envio_real(
    chamado_id: int,
    regra_id: str,
    prazo_dias_uteis: int = 1,
    email_assunto: str = "",
    graph_message_id: str = "",
    graph_conversation_id: str = "",
    graph_internet_message_id: str = "",
) -> dict:
    agora = _agora()
    prazo = _adicionar_dias_uteis(
        agora,
        int(prazo_dias_uteis or 0),
    )

    with _conectar() as conn:
        conn.execute(
            """
            UPDATE acoes_operacionais
               SET estado = 'AGUARDANDO_RESPOSTA',
                   enviado_em = ?,
                   prazo_resposta_em = ?,
                   resposta_recebida_em = NULL,
                   atualizado_em = ?,
                   erro_envio = NULL,
                   redmine_atualizado_em = NULL,
                   redmine_erro = NULL,
                   email_assunto = ?,
                   graph_message_id = ?,
                   graph_conversation_id = ?,
                   graph_internet_message_id = ?,
                   resposta_graph_message_id = NULL,
                   resposta_remetente = NULL,
                   resposta_assunto = NULL,
                   resposta_corpo = NULL,
                   monitorado_em = NULL
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (
                _iso(agora),
                _iso(prazo),
                _iso(agora),
                str(email_assunto or ""),
                str(graph_message_id or ""),
                str(graph_conversation_id or ""),
                str(graph_internet_message_id or ""),
                int(chamado_id),
                str(regra_id),
            ),
        )

    return obter_acompanhamento(
        chamado_id,
        regra_id,
    )


def registrar_falha_envio(
    chamado_id: int,
    regra_id: str,
    erro: str,
) -> dict:
    agora = _agora()

    with _conectar() as conn:
        conn.execute(
            """
            UPDATE acoes_operacionais
               SET estado = 'ERRO_ENVIO',
                   atualizado_em = ?,
                   erro_envio = ?
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (
                _iso(agora),
                str(erro)[:1500],
                int(chamado_id),
                str(regra_id),
            ),
        )

    return obter_acompanhamento(
        chamado_id,
        regra_id,
    )



def marcar_redmine_atualizado(
    chamado_id: int,
    regra_id: str,
) -> dict:
    agora = _agora()

    with _conectar() as conn:
        conn.execute(
            """
            UPDATE acoes_operacionais
               SET redmine_atualizado_em = ?,
                   redmine_erro = NULL,
                   atualizado_em = ?
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (
                _iso(
                    agora
                ),
                _iso(
                    agora
                ),
                int(
                    chamado_id
                ),
                str(
                    regra_id
                ),
            ),
        )

    return obter_acompanhamento(
        chamado_id,
        regra_id,
    )


def registrar_falha_redmine(
    chamado_id: int,
    regra_id: str,
    erro: str,
) -> dict:
    agora = _agora()

    with _conectar() as conn:
        conn.execute(
            """
            UPDATE acoes_operacionais
               SET redmine_erro = ?,
                   atualizado_em = ?
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (
                str(
                    erro
                )[:1500],
                _iso(
                    agora
                ),
                int(
                    chamado_id
                ),
                str(
                    regra_id
                ),
            ),
        )

    return obter_acompanhamento(
        chamado_id,
        regra_id,
    )



def marcar_status_redmine(
    chamado_id: int,
    regra_id: str,
    status_nome: str,
) -> dict:
    """
    Persiste o status que a própria EDNNA confirmou via PUT no Redmine.

    Esse valor é usado como fonte mais recente enquanto o snapshot
    geral do painel ainda estiver desatualizado.
    """
    agora = _agora()

    with _conectar() as conn:
        conn.execute(
            """
            UPDATE acoes_operacionais
               SET redmine_status_nome = ?,
                   redmine_status_atualizado_em = ?,
                   atualizado_em = ?
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (
                str(
                    status_nome
                    or ""
                ).strip(),
                _iso(
                    agora
                ),
                _iso(
                    agora
                ),
                int(
                    chamado_id
                ),
                str(
                    regra_id
                ),
            ),
        )

    return obter_acompanhamento(
        chamado_id,
        regra_id,
    )


def listar_acoes_aguardando_resposta() -> list[dict]:
    inicializar_acompanhamento()

    with _conectar() as conn:
        rows = conn.execute(
            """
            SELECT *
              FROM acoes_operacionais
             WHERE estado IN ('AGUARDANDO_RESPOSTA', 'PRAZO_VENCIDO')
               AND enviado_em IS NOT NULL
             ORDER BY enviado_em ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def marcar_monitorado(
    chamado_id: int,
    regra_id: str,
    *,
    graph_message_id: str = "",
    graph_conversation_id: str = "",
    graph_internet_message_id: str = "",
) -> dict:
    agora = _iso(_agora())

    with _conectar() as conn:
        conn.execute(
            """
            UPDATE acoes_operacionais
               SET monitorado_em = ?,
                   graph_message_id = CASE WHEN ? <> '' THEN ? ELSE graph_message_id END,
                   graph_conversation_id = CASE WHEN ? <> '' THEN ? ELSE graph_conversation_id END,
                   graph_internet_message_id = CASE WHEN ? <> '' THEN ? ELSE graph_internet_message_id END,
                   atualizado_em = ?
             WHERE chamado_id = ?
               AND regra_id = ?
            """,
            (
                agora,
                graph_message_id, graph_message_id,
                graph_conversation_id, graph_conversation_id,
                graph_internet_message_id, graph_internet_message_id,
                agora,
                int(chamado_id),
                str(regra_id),
            ),
        )

    return obter_acompanhamento(chamado_id, regra_id)


def registrar_resposta(
    chamado_id: int,
    regra_id: str,
    *,
    graph_message_id: str = "",
    remetente: str = "",
    assunto: str = "",
    corpo: str = "",
    recebida_em: str = "",
) -> dict:
    inicializar_acompanhamento()
    agora = _agora()

    try:
        recebida = datetime.fromisoformat(recebida_em.replace("Z", "+00:00")) if recebida_em else agora
        if recebida.tzinfo is None:
            recebida = recebida.replace(tzinfo=TZ_BRASIL)
        recebida = recebida.astimezone(TZ_BRASIL)
    except Exception:
        recebida = agora

    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO acoes_operacionais (
                chamado_id, regra_id, estado, resposta_recebida_em, atualizado_em,
                resposta_graph_message_id, resposta_remetente, resposta_assunto,
                resposta_corpo, monitorado_em
            )
            VALUES (?, ?, 'RESPOSTA_RECEBIDA', ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chamado_id, regra_id)
            DO UPDATE SET
                estado = 'RESPOSTA_RECEBIDA',
                resposta_recebida_em = excluded.resposta_recebida_em,
                resposta_graph_message_id = excluded.resposta_graph_message_id,
                resposta_remetente = excluded.resposta_remetente,
                resposta_assunto = excluded.resposta_assunto,
                resposta_corpo = excluded.resposta_corpo,
                monitorado_em = excluded.monitorado_em,
                atualizado_em = excluded.atualizado_em
            """,
            (
                int(chamado_id), str(regra_id), _iso(recebida), _iso(agora),
                str(graph_message_id or ""), str(remetente or "")[:500],
                str(assunto or "")[:1000], str(corpo or "")[:12000], _iso(agora),
            ),
        )

    return obter_acompanhamento(chamado_id, regra_id)


def rotulo_estado(
    estado: str,
) -> str:
    return {
        "RASCUNHO": "⚪ Rascunho",
        "ENVIANDO": "🔵 Enviando",
        "ERRO_ENVIO": "🔴 Erro no envio",
        "AGUARDANDO_RESPOSTA": "🟡 Aguardando resposta",
        "PRAZO_VENCIDO": "🔴 Prazo de resposta vencido",
        "RESPOSTA_RECEBIDA": "🟢 Resposta recebida",
    }.get(
        str(estado or ""),
        str(estado or "Sem estado"),
    )


def registrar_responsabilidade_ednna(chamado_id: int, regra_id: str, anterior_id: int | None, anterior_nome: str = "") -> None:
    agora = _agora()
    with _conectar() as conn:
        conn.execute(
            """UPDATE acoes_operacionais
               SET responsavel_anterior_id = COALESCE(responsavel_anterior_id, ?),
                   responsavel_anterior_nome = CASE WHEN COALESCE(responsavel_anterior_nome, '') = '' THEN ? ELSE responsavel_anterior_nome END,
                   ednna_assumiu_em = COALESCE(ednna_assumiu_em, ?),
                   atualizado_em = ?
             WHERE chamado_id = ? AND regra_id = ?""",
            (anterior_id, str(anterior_nome or ""), _iso(agora), _iso(agora), int(chamado_id), str(regra_id)),
        )


def obter_responsavel_original_cancelamento(chamado_id: int) -> dict:
    """Recupera o primeiro responsável humano preservado por qualquer etapa do chamado."""
    inicializar_acompanhamento()
    with _conectar() as conn:
        row = conn.execute(
            """SELECT responsavel_anterior_id, responsavel_anterior_nome
                 FROM acoes_operacionais
                WHERE chamado_id = ?
                  AND responsavel_anterior_id IS NOT NULL
                  AND responsavel_anterior_id <> ?
                ORDER BY COALESCE(ednna_assumiu_em, atualizado_em) ASC
                LIMIT 1""",
            (int(chamado_id), int(os.getenv('REDMINE_EDNNA_USER_ID','166') or 166)),
        ).fetchone()
    if not row:
        return {}
    return {'id': row['responsavel_anterior_id'], 'nome': row['responsavel_anterior_nome'] or ''}
