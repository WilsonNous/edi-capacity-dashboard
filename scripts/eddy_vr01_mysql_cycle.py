"""EDDY VR01 controlled MySQL cycle.

Sync Redmine to MySQL, then assess stored snapshots. Never use SQLite or send mail.
"""
from __future__ import annotations

import json

from ednna.eddy_vr_mysql_sync import sincronizar_carteira_vr_mysql
from ednna.eddy_vr_mysql_operation import operacao_vr_mysql


def executar_ciclo_vr01() -> dict:
    sync = sincronizar_carteira_vr_mysql()
    if not sync["cobertura_completa"]:
        return {
            "estado": "BLOQUEADO_SINCRONIZACAO_PARCIAL",
            "sincronizacao": sync,
            "operacao": None,
            "envios_realizados": 0,
            "redmine_escritas": 0,
        }
    operation = operacao_vr_mysql()
    imported = set(sync["importados"]) | set(sync.get("reutilizados_mysql", []))
    observed = {item["chamado_id"] for item in operation["chamados"]}
    if not imported.issubset(observed):
        return {
            "estado": "BLOQUEADO_DIVERGENCIA_MYSQL",
            "sincronizacao": sync,
            "operacao": None,
            "envios_realizados": 0,
            "redmine_escritas": 0,
        }
    return {
        "estado": "AVALIADO_SOMENTE_LEITURA",
        "sincronizacao": sync,
        "operacao": operation,
        "envios_realizados": 0,
        "redmine_escritas": 0,
    }


if __name__ == "__main__":
    print(json.dumps(executar_ciclo_vr01(), ensure_ascii=False, indent=2, default=str))
