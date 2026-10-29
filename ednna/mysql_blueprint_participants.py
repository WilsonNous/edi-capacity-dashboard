"""MySQL read model for Blueprint participants; no SQLite on VR01 read path.

Migration is explicit, read-only on source and atomic on destination.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ednna.mysql_storage import connect


DDL = """CREATE TABLE IF NOT EXISTS eddy_blueprint_participants (
    source_id BIGINT NOT NULL PRIMARY KEY,
    cliente VARCHAR(255) NOT NULL,
    nome TEXT NULL,
    area VARCHAR(255) NULL,
    email VARCHAR(320) NULL,
    telefone TEXT NULL,
    andamento VARCHAR(32) NULL,
    status_report VARCHAR(32) NULL,
    documento_id BIGINT NOT NULL,
    chamado_id BIGINT NOT NULL,
    ativo TINYINT NOT NULL,
    fonte_arquivo TEXT NULL,
    attachment_id BIGINT NULL,
    importado_em VARCHAR(64) NULL,
    KEY idx_bp_cliente_ativo (cliente, ativo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def preparar():
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)


def selecionar_contatos_cliente_mysql(cliente, limite=10, area_preferida="FINANCEIRO"):
    from ednna.blueprint_knowledge import _norm
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT cliente, nome, area, email, telefone, andamento,
                status_report, documento_id, chamado_id, ativo, fonte_arquivo,
                attachment_id, importado_em
                FROM eddy_blueprint_participants
                WHERE cliente=%s AND ativo=1
                ORDER BY importado_em DESC, source_id ASC""", (cliente,))
            columns = [x[0] for x in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    unique, seen = [], set()
    for row in rows:
        email = str(row.get("email") or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(row)
    pref = _norm(area_preferida)
    def score(row):
        area = _norm(row.get("area"))
        andamento = _norm(row.get("andamento")) in {"SIM", "S", "YES", "TRUE", "1"}
        status = _norm(row.get("status_report")) in {"SIM", "S", "YES", "TRUE", "1"}
        return (0 if area == pref else (1 if "GERENTE/COORD" in area else 2),
                0 if andamento else 1, 0 if status else 1)
    unique.sort(key=score)
    return unique[:max(1, int(limite or 1))]


def importar_participantes_sqlite(caminho, *, aplicar=False):
    """Only import a fully readable source; never overwrite or repair SQLite."""
    path = Path(caminho)
    if not path.is_file():
        raise FileNotFoundError("Arquivo SQLite de origem inexistente")
    uri = path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as source:
        check = source.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise ValueError("SQLite corrompido: preservar arquivo e recuperar de backup")
        rows = source.execute("""SELECT p.id, p.cliente, p.nome, p.area, p.email,
            p.telefone, p.andamento, p.status_report, p.documento_id,
            p.chamado_id, p.ativo, d.nome_arquivo, d.attachment_id,
            d.importado_em
            FROM blueprint_participantes p JOIN blueprint_documentos d
            ON d.id=p.documento_id ORDER BY p.id""").fetchall()
    if not aplicar:
        return {"modo": "DRY_RUN", "participantes": len(rows), "mysql_escritas": 0}
    preparar()
    with connect() as conn:
        with conn.cursor() as cursor:
            for row in rows:
                cursor.execute("""INSERT INTO eddy_blueprint_participants
                    (source_id, cliente, nome, area, email, telefone, andamento,
                     status_report, documento_id, chamado_id, ativo, fonte_arquivo,
                     attachment_id, importado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE cliente=VALUES(cliente),
                    nome=VALUES(nome), area=VALUES(area), email=VALUES(email),
                    telefone=VALUES(telefone), andamento=VALUES(andamento),
                    status_report=VALUES(status_report), ativo=VALUES(ativo),
                    fonte_arquivo=VALUES(fonte_arquivo),
                    attachment_id=VALUES(attachment_id),
                    importado_em=VALUES(importado_em)""", row)
    return {"modo": "IMPORTADO", "participantes": len(rows), "mysql_escritas": len(rows)}
