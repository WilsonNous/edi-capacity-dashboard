"""EDDY: explicit, non-destructive archival migration from legacy SQLite to MySQL.

Default mode is inventory only. --apply requires a verified SQLite copy.
No operational rules are activated or switched by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

# Explicit scope: never copy runtime locks, secrets or transient coordination.
TABLES = (
    "analises_primeiro_combate",
    "classificacoes_demandas",
    "aprendizados_operacionais",
    "revisoes_regras_operacionais",
    "regras_treinaveis",
    "testes_regras_treinaveis",
)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def inventariar(path: Path) -> tuple[list[dict], list[tuple[str, str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = path.resolve().as_uri() + "?mode=ro"
    records = []
    report = []
    with sqlite3.connect(uri, uri=True, timeout=5) as db:
        db.row_factory = sqlite3.Row
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError("SQLite integrity_check failed; recover a verified copy first")
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in TABLES:
            if table not in existing:
                report.append({"tabela": table, "estado": "AUSENTE", "registros": 0})
                continue
            if not _IDENTIFIER.fullmatch(table):
                raise ValueError("invalid table identifier")
            count = 0
            for row in db.execute(f'SELECT * FROM "{table}"'):
                data = dict(row)
                encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
                digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
                records.append((table, digest, encoded))
                count += 1
            report.append({"tabela": table, "estado": "INTEGRA", "registros": count})
    return report, records


def arquivar(records: list[tuple[str, str, str]]) -> dict:
    from ednna.mysql_storage import connect
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eddy_legacy_knowledge_archive (
                    source_table VARCHAR(128) NOT NULL,
                    payload_sha256 CHAR(64) NOT NULL,
                    payload_json LONGTEXT NOT NULL,
                    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_table, payload_sha256)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            for table, digest, payload in records:
                cursor.execute("""
                    INSERT INTO eddy_legacy_knowledge_archive
                    (source_table, payload_sha256, payload_json)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE payload_sha256 = VALUES(payload_sha256)
                """, (table, digest, payload))
            # Verify every content hash is present, not merely an aggregate count.
            for table, digest, _ in records:
                cursor.execute("""
                    SELECT 1 FROM eddy_legacy_knowledge_archive
                    WHERE source_table=%s AND payload_sha256=%s
                """, (table, digest))
                if cursor.fetchone() is None:
                    raise RuntimeError("MySQL archive reconciliation failed")
    return {"verificados": len(records), "modo": "ARQUIVO_HISTORICO_SEM_ATIVACAO"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-copy", type=Path, required=True, help="Offline copy, never live ednna.db")
    parser.add_argument("--apply", action="store_true", help="Write archive to MySQL after integrity verification")
    args = parser.parse_args()
    if args.sqlite_copy.name == "ednna.db":
        parser.error("Use a named backup copy, not the live ednna.db")
    report, records = inventariar(args.sqlite_copy)
    result = {"tabelas": report, "registros": len(records), "modo": "INVENTARIO"}
    if args.apply:
        result["arquivo_mysql"] = arquivar(records)
        result["modo"] = "ARQUIVADO"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
