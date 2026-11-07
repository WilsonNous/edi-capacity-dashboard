"""MySQL-backed DB-API compatibility for legacy EDDY action SQL.

Only the fixed SQL statements in acompanhamento_acoes are supported.
"""
from __future__ import annotations

import re
from ednna.mysql_storage import connect

_FIELDS = {
    "chamado_id": "BIGINT NOT NULL", "regra_id": "VARCHAR(191) NOT NULL",
    "estado": "VARCHAR(64) NOT NULL DEFAULT 'RASCUNHO'",
    "responsavel_anterior_id": "BIGINT NULL", "redmine_pendente_assigned_to_id": "BIGINT NULL",
    "followup_count": "INT DEFAULT 0", "redmine_tentativas": "INT DEFAULT 0",
    "envio_confirmado": "INT DEFAULT 0",
}
_TEXT = """enviado_em prazo_resposta_em resposta_recebida_em atualizado_em observacao erro_envio
redmine_atualizado_em redmine_erro redmine_status_nome redmine_status_atualizado_em
email_assunto graph_message_id graph_conversation_id graph_internet_message_id
resposta_graph_message_id resposta_remetente resposta_assunto resposta_corpo monitorado_em
responsavel_anterior_nome ednna_assumiu_em evidencia_anexada_em evidencia_filename
evidencia_erro followup_ultimo_em redmine_pendente_nota redmine_pendente_status""".split()
for _field in _TEXT:
    _FIELDS[_field] = "TEXT NULL" if _field in {
        "observacao", "erro_envio", "redmine_erro", "resposta_corpo",
        "redmine_pendente_nota", "evidencia_erro"} else "VARCHAR(1024) NULL"
for _field in ("enviado_em", "prazo_resposta_em", "resposta_recebida_em",
               "atualizado_em", "redmine_atualizado_em", "redmine_status_atualizado_em",
               "monitorado_em", "ednna_assumiu_em", "evidencia_anexada_em",
               "followup_ultimo_em"):
    _FIELDS[_field] = "VARCHAR(40) NULL"

DDL = ("CREATE TABLE IF NOT EXISTS eddy_acoes_operacionais (" +
       ", ".join(f"`{key}` {definition}" for key, definition in _FIELDS.items()) +
       ", PRIMARY KEY (chamado_id, regra_id), KEY idx_eddy_acoes_estado (estado), "
       "KEY idx_eddy_acoes_regra (regra_id, envio_confirmado), "
       "KEY idx_eddy_acoes_envio (enviado_em)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")


class Result:
    def __init__(self, rows, description):
        self.rows = [dict(zip([col[0] for col in description], row)) for row in rows] if description else []
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self):
        self.context = connect()
        self.conn = self.context.__enter__()
        self.in_transaction = False
        self.closed = False
        self.lock_name = None

    def execute(self, query, params=()):
        normalized = query.strip()
        command = normalized.upper()
        if command == "BEGIN IMMEDIATE":
            self.in_transaction = True
            return Result([], None)
        if command == "COMMIT":
            self.conn.commit()
            self._unlock()
            self.in_transaction = False
            return Result([], None)
        if command == "ROLLBACK":
            self.conn.rollback()
            self._unlock()
            self.in_transaction = False
            return Result([], None)
        if command.startswith("CREATE TABLE") or command.startswith("ALTER TABLE") or command.startswith("PRAGMA"):
            raise RuntimeError("MySQL schema must be initialized separately")
        if not re.match(r"^(SELECT|INSERT|UPDATE)\\b", command):
            raise RuntimeError("Unsupported operational SQL")
        if self.in_transaction and command.startswith("SELECT") and "FROM ACOES_OPERACIONAIS" in command and self.lock_name is None:
            self.lock_name = f"eddy_action_{int(params[0])}_{str(params[1])}"[:64]
            with self.conn.cursor() as lock_cursor:
                lock_cursor.execute("SELECT GET_LOCK(%s, 10)", (self.lock_name,))
                if lock_cursor.fetchone()[0] != 1:
                    self.lock_name = None
                    raise RuntimeError("MYSQL_ACTION_LOCK_TIMEOUT")
        query = re.sub(r"\\bacoes_operacionais\\b", "eddy_acoes_operacionais", query)
        query = query.replace("?", "%s")
        query = re.sub(r"ON CONFLICT\\s*\\(chamado_id,\\s*regra_id\\)\\s*DO UPDATE SET",
                       "ON DUPLICATE KEY UPDATE", query, flags=re.I)
        query = re.sub(r"excluded\\.(\\w+)", r"VALUES(\\1)", query, flags=re.I)
        with self.conn.cursor() as cursor:
            cursor.execute(query, params)
            desc = cursor.description
            rows = cursor.fetchall() if desc else []
        if not self.in_transaction:
            self.conn.commit()
        return Result(rows, desc)

    def _unlock(self):
        if self.lock_name:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (self.lock_name,))
            self.lock_name = None

    def close(self):
        if not self.closed:
            self._unlock()
            self.context.__exit__(None, None, None)
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._unlock()
            self.context.__exit__(exc_type, exc, tb)
            self.closed = True
        else:
            self.close()


def initialize():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)


def connection():
    return Connection()
