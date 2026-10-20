"""VR01 worker entrypoint with MySQL advisory lock and fail-closed behavior.

Call from EDDY's existing scheduler. Does not schedule itself or send emails.
"""
from __future__ import annotations

import json
import logging

from ednna.mysql_storage import connect
from scripts.eddy_vr01_mysql_cycle import executar_ciclo_vr01

LOGGER = logging.getLogger(__name__)
LOCK_NAME = "eddy:vr01:mysql:cycle"


def executar_worker_vr01() -> dict:
    """Only one active VR01 cycle across Azure instances."""
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s)", (LOCK_NAME, 0))
            row = cursor.fetchone()
            if not row or row[0] != 1:
                return {"estado": "IGNORADO_EXECUCAO_CONCORRENTE", "envios_realizados": 0}
        try:
            result = executar_ciclo_vr01()
            LOGGER.info(
                "[EDDY-VR01] ciclo=%s importados=%s falhas=%s",
                result["estado"],
                len(result["sincronizacao"]["importados"]),
                len(result["sincronizacao"]["falhas"]),
            )
            return result
        finally:
            # MySQL locks are connection-scoped. Always release before returning
            # the pooled/managed connection; connection closure also releases it.
            with conn.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))


if __name__ == "__main__":
    print(json.dumps(executar_worker_vr01(), ensure_ascii=False, default=str))
