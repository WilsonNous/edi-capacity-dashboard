"""VR01 worker with isolated MySQL advisory-lock session and fail-closed behavior.

The lock session is never used for business transactions and is not committed
on exit. External dispatch remains guarded by its independent readiness gates.
"""
from __future__ import annotations

import json
import logging

import pymysql

from ednna.mysql_storage import connection_options
from scripts.eddy_vr01_mysql_cycle import executar_ciclo_vr01

LOGGER = logging.getLogger(__name__)
LOCK_NAME = "eddy:vr01:mysql:cycle"


def executar_worker_vr01() -> dict:
    """Acquire an isolated advisory lock; do not commit on a dropped lock session."""
    options = connection_options()
    options["autocommit"] = True
    conn = pymysql.connect(**options)
    acquired = False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            tls = cursor.fetchone()
            if not tls or not tls[1]:
                raise RuntimeError("MySQL TLS is required for VR01 advisory lock")
            cursor.execute("SELECT GET_LOCK(%s, %s)", (LOCK_NAME, 0))
            row = cursor.fetchone()
            if not row or row[0] != 1:
                return {"estado": "IGNORADO_EXECUCAO_CONCORRENTE", "envios_realizados": 0}
            acquired = True
        result = executar_ciclo_vr01()
        LOGGER.info(
            "[EDDY-VR01] ciclo=%s importados=%s falhas=%s",
            result["estado"],
            len(result["sincronizacao"]["importados"]),
            len(result["sincronizacao"]["falhas"]),
        )
        return result
    finally:
        if acquired and conn.open:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
            except pymysql.MySQLError as exc:
                LOGGER.warning("[EDDY-VR01] falha ao liberar lock MySQL: %s", type(exc).__name__)
        try:
            conn.close()
        except pymysql.MySQLError:
            pass


if __name__ == "__main__":
    print(json.dumps(executar_worker_vr01(), ensure_ascii=False, default=str))
