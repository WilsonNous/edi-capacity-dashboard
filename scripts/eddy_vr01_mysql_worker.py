"""VR01 worker with isolated MySQL advisory-lock session and fail-closed behavior.

The lock session is never used for business transactions and is not committed
on exit. External dispatch remains guarded by its independent readiness gates.
"""
from __future__ import annotations

import json
import logging
import threading

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
    lock_connection_id = None
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
            cursor.execute("SELECT CONNECTION_ID()")
            lock_connection_id = cursor.fetchone()[0]
        # Keep the dedicated advisory-lock connection alive while slow Redmine/Graph
        # requests run. Only the heartbeat thread touches this connection until joined.
        stop_heartbeat = threading.Event()
        heartbeat_errors = []

        def keep_lock_alive():
            while not stop_heartbeat.wait(20):
                try:
                    conn.ping(reconnect=False)
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT CONNECTION_ID(), IS_USED_LOCK(%s)", (LOCK_NAME,))
                        session_id, holder_id = cursor.fetchone()
                    if session_id != lock_connection_id or holder_id != lock_connection_id:
                        raise RuntimeError("VR01 advisory lock ownership lost during cycle")
                except (pymysql.MySQLError, RuntimeError) as exc:
                    heartbeat_errors.append(exc)
                    LOGGER.error("[EDDY-VR01] advisory lock heartbeat failed: %s", type(exc).__name__)
                    break

        heartbeat = threading.Thread(target=keep_lock_alive, name="vr01-lock-heartbeat", daemon=True)
        heartbeat.start()
        try:
            result = executar_ciclo_vr01()
        finally:
            stop_heartbeat.set()
            heartbeat.join()
        if heartbeat_errors:
            raise RuntimeError("VR01 advisory lock session lost during cycle") from heartbeat_errors[0]
        try:
            conn.ping(reconnect=False)
            with conn.cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID(), IS_USED_LOCK(%s)", (LOCK_NAME,))
                session_id, holder_id = cursor.fetchone()
            if session_id != lock_connection_id or holder_id != lock_connection_id:
                raise RuntimeError("VR01 advisory lock ownership lost during cycle")
        except pymysql.MySQLError as exc:
            raise RuntimeError("VR01 advisory lock session lost during cycle") from exc
        LOGGER.info(
            "[EDDY-VR01] ciclo=%s importados=%s falhas=%s",
            result["estado"],
            len((result.get("sincronizacao") or {}).get("importados") or []),
            len((result.get("sincronizacao") or {}).get("falhas") or []),
        )
        return result
    finally:
        if acquired and conn.open:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
            except pymysql.MySQLError as exc:
                LOGGER.warning("[EDDY-VR01] falha ao liberar lock MySQL: tipo=%s errno=%s conexao=%s", type(exc).__name__, exc.args[0] if exc.args else None, lock_connection_id)
        try:
            conn.close()
        except pymysql.MySQLError:
            pass


if __name__ == "__main__":
    print(json.dumps(executar_worker_vr01(), ensure_ascii=False, default=str))
