"""MySQL foundation for EDDY: conservative schema and storage health.

Does not switch operational persistence. External effects remain disabled until
the operational modules are migrated and idempotency is reconciled.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import pymysql

SCHEMA_VERSION = 2

DDL = (
    """CREATE TABLE IF NOT EXISTS eddy_chamados (
        id BIGINT NOT NULL PRIMARY KEY,
        cliente VARCHAR(255) NULL,
        origem VARCHAR(191) NULL,
        responsavel VARCHAR(255) NULL,
        projeto VARCHAR(255) NULL,
        tipo VARCHAR(191) NULL,
        estado VARCHAR(191) NULL,
        prioridade VARCHAR(191) NULL,
        assunto TEXT NULL,
        criado_em VARCHAR(40) NULL,
        alterado_em VARCHAR(40) NULL,
        tempo_aberto_dias DOUBLE NULL,
        payload_json LONGTEXT NULL,
        sincronizado_em VARCHAR(40) NOT NULL,
        KEY idx_eddy_chamados_estado (estado),
        KEY idx_eddy_chamados_alterado (alterado_em)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_journals (
        id BIGINT NOT NULL PRIMARY KEY,
        chamado_id BIGINT NOT NULL,
        autor VARCHAR(255) NULL,
        criado_em VARCHAR(40) NULL,
        notas LONGTEXT NULL,
        detalhes_json LONGTEXT NULL,
        sincronizado_em VARCHAR(40) NOT NULL,
        KEY idx_eddy_journals_chamado (chamado_id),
        CONSTRAINT fk_eddy_journal_chamado FOREIGN KEY (chamado_id)
            REFERENCES eddy_chamados(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_schema_versions (
        version INT NOT NULL PRIMARY KEY,
        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_external_evidence (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        source VARCHAR(32) NOT NULL,
        external_id VARCHAR(191) NOT NULL,
        chamado_id BIGINT NULL,
        regra_id VARCHAR(191) NULL,
        evidence_type VARCHAR(64) NOT NULL,
        observed_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        payload_sha256 CHAR(64) NULL,
        UNIQUE KEY uq_external_evidence (source, external_id, evidence_type),
        KEY idx_evidence_chamado (chamado_id, observed_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_storage_metrics (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        recorded_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        database_bytes BIGINT UNSIGNED NOT NULL,
        table_count INT UNSIGNED NOT NULL,
        KEY idx_storage_recorded (recorded_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
)


def connection_options() -> dict:
    required = ("EDDY_DB_HOST", "EDDY_DB_USER", "EDDY_DB_PASSWORD", "EDDY_DB_NAME")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ValueError("Missing MySQL settings: " + ", ".join(missing))
    mode = os.getenv("EDDY_DB_SSL_MODE", "REQUIRED").upper()
    if mode not in {"REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"}:
        raise ValueError("Invalid EDDY_DB_SSL_MODE")
    ca = os.getenv("EDDY_DB_SSL_CA")
    if mode != "REQUIRED" and not ca:
        raise ValueError("EDDY_DB_SSL_CA required for certificate verification")
    return {
        "host": os.environ["EDDY_DB_HOST"],
        "port": int(os.getenv("EDDY_DB_PORT", "3306")),
        "user": os.environ["EDDY_DB_USER"],
        "password": os.environ["EDDY_DB_PASSWORD"],
        "database": os.environ["EDDY_DB_NAME"],
        "charset": "utf8mb4",
        "autocommit": False,
        "connect_timeout": 10,
        "read_timeout": 10,
        "write_timeout": 10,
        "ssl": {"ca": ca} if ca else {},
        "ssl_verify_cert": mode != "REQUIRED",
        "ssl_verify_identity": mode == "VERIFY_IDENTITY",
    }


@contextmanager
def connect():
    conn = pymysql.connect(**connection_options())
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            row = cursor.fetchone()
            if not row or not row[1]:
                raise RuntimeError("MySQL TLS is required")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def bootstrap() -> None:
    """Idempotent DDL for foundation tables only; never clears existing data."""
    with connect() as conn:
        with conn.cursor() as cursor:
            for statement in DDL:
                cursor.execute(statement)
            cursor.execute(
                "INSERT IGNORE INTO eddy_schema_versions (version) VALUES (%s)",
                (SCHEMA_VERSION,),
            )


def storage_health() -> dict:
    """Read-only storage sizing; avoids scanning operational payloads."""
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(SUM(data_length + index_length), 0), COUNT(*)
                   FROM information_schema.tables WHERE table_schema = %s""",
                (os.environ["EDDY_DB_NAME"],),
            )
            size, count = cursor.fetchone()
            return {"database_bytes": int(size), "table_count": int(count)}


def record_storage_health() -> dict:
    health = storage_health()
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO eddy_storage_metrics (database_bytes, table_count)
                   VALUES (%s, %s)""",
                (health["database_bytes"], health["table_count"]),
            )
    return health
