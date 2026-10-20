"""Periodic autonomous VR01 observation on MySQL, independent of Streamlit sessions.

This worker NEVER enables outbound email or Redmine writes. All instances may
start it: the existing MySQL advisory lock serializes individual cycles.
"""
from __future__ import annotations

import json
import logging
import os
import time

from scripts.eddy_vr01_mysql_worker import executar_worker_vr01

LOG = logging.getLogger("eddy.vr01.scheduler")


def intervalo_segundos(raw: str | None) -> int:
    try:
        value = int(raw or "900")
    except (ValueError, TypeError):
        raise ValueError("EDDY_VR01_INTERVAL_SECONDS must be an integer") from None
    if value < 300:
        raise ValueError("EDDY_VR01_INTERVAL_SECONDS must be >= 300")
    return value


def executar_uma_vez() -> dict:
    result = executar_worker_vr01()
    sync = result.get("sincronizacao") or {}
    LOG.info(
        "[EDDY-VR01-SCHEDULER] %s",
        json.dumps({
            "estado": result.get("estado"),
            "abertos_consultados": sync.get("abertos_consultados"),
            "vr_identificados": sync.get("vr_identificados"),
            "importados": len(sync.get("importados") or []),
            "reutilizados_mysql": len(sync.get("reutilizados_mysql") or []),
            "falhas": len(sync.get("falhas") or []),
            "envios_realizados": result.get("envios_realizados", 0),
            "redmine_escritas": result.get("redmine_escritas", 0),
        }, ensure_ascii=False, default=str),
    )
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if os.getenv("EDDY_DB_ENGINE", "").lower() != "mysql":
        raise SystemExit("[EDDY-VR01-SCHEDULER] MySQL obrigatório; execução recusada")
    interval = intervalo_segundos(os.getenv("EDDY_VR01_INTERVAL_SECONDS"))
    LOG.info("[EDDY-VR01-SCHEDULER] iniciado; intervalo_s=%s; somente_leitura=true", interval)
    while True:
        try:
            executar_uma_vez()
        except Exception as exc:
            LOG.exception("[EDDY-VR01-SCHEDULER] falha segura: %s", type(exc).__name__)
        time.sleep(interval)


if __name__ == "__main__":
    main()
