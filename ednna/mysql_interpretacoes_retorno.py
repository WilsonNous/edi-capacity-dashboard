"""Idempotent MySQL storage for interpreted Graph replies."""
from __future__ import annotations

import hashlib
import json

from ednna.mysql_storage import connect

DDL = """CREATE TABLE IF NOT EXISTS eddy_interpretacoes_retorno (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    chamado_id BIGINT NOT NULL,
    regra_id VARCHAR(191) NOT NULL,
    digest CHAR(64) NOT NULL,
    graph_message_id VARCHAR(255) NOT NULL DEFAULT '',
    classificacao VARCHAR(191) NOT NULL,
    decisao_json TEXT NOT NULL,
    criado_em VARCHAR(40) NOT NULL,
    UNIQUE KEY uq_eddy_interpretacao (chamado_id, regra_id, digest),
    KEY idx_eddy_interpretacao_recente (chamado_id, regra_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def registrar(chamado_id, regra_id, *, corpo, assunto="", recebido_em="", graph_message_id=""):
    from ednna.interpretacao_retorno import interpretar_retorno
    from datetime import datetime, timezone
    decisao = interpretar_retorno(corpo, assunto=assunto, recebido_em=recebido_em)
    digest = hashlib.sha256((str(graph_message_id) + "\\0" + str(corpo)).encode()).hexdigest()
    payload = json.dumps(decisao, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 60000:
        raise ValueError("Interpretacao excede limite de armazenamento")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("""INSERT IGNORE INTO eddy_interpretacoes_retorno
                (chamado_id, regra_id, digest, graph_message_id, classificacao, decisao_json, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (int(chamado_id), str(regra_id), digest, str(graph_message_id)[:255],
                 str(decisao["classificacao"])[:191], payload,
                 datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return decisao


def ultima(chamado_id, regra_id=""):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            if regra_id:
                cur.execute("""SELECT decisao_json FROM eddy_interpretacoes_retorno
                    WHERE chamado_id=%s AND regra_id=%s ORDER BY id DESC LIMIT 1""",
                    (int(chamado_id), str(regra_id)))
            else:
                cur.execute("""SELECT decisao_json FROM eddy_interpretacoes_retorno
                    WHERE chamado_id=%s ORDER BY id DESC LIMIT 1""", (int(chamado_id),))
            row = cur.fetchone()
    return json.loads(row[0]) if row else {}
