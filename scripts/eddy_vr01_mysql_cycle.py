"""EDDY VR01 controlled MySQL cycle.

Sync Redmine to MySQL, then assess stored snapshots. Never use SQLite or send mail.
"""
from __future__ import annotations

import json

from ednna.eddy_vr_mysql_sync import sincronizar_carteira_vr_mysql
from ednna.eddy_vr_mysql_operation import operacao_vr_mysql
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.eddy_vr_action_queue import registrar_intencoes


def executar_ciclo_vr01() -> dict:
    sync = sincronizar_carteira_vr_mysql()
    if not sync["cobertura_completa"]:
        # Read-only observability must survive Redmine outages; stale data must
        # never authorize sends, follow-ups or Redmine writes.
        try:
            operation = operacao_vr_mysql()
        except Exception as exc:
            return {
                "estado": "BLOQUEADO_MYSQL_INDISPONIVEL",
                "sincronizacao": sync, "operacao": None,
                "erro": type(exc).__name__,
                "envios_realizados": 0, "redmine_escritas": 0,
            }
        operation["carteira_confirmada_agora"] = False
        operation["aviso"] = "Redmine indisponível ou parcial; leitura MySQL histórica. Ações externas bloqueadas."
        return {
            "estado": "DEGRADADO_MYSQL_SOMENTE_LEITURA",
            "sincronizacao": sync, "operacao": operation,
            "envios_realizados": 0, "redmine_escritas": 0,
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
    # Plan intents only after complete Redmine coverage and consistent MySQL snapshots.
    snapshots = []
    try:
        for issue_id in sorted(imported):
            stored = carregar_snapshot(issue_id)
            if not stored:
                raise ValueError("snapshot missing")
            payload = stored["chamado"].get("payload_json")
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict) or payload.get("_eddy_journals_completos") is not True:
                raise ValueError("incomplete journal evidence")
            journals = [{"notes": j.get("notas") or "", "created_on": j.get("criado_em")}
                        for j in stored["journals"]]
            snapshots.append((payload, journals))
        queue = registrar_intencoes(snapshots)
    except Exception as exc:
        return {"estado": "BLOQUEADO_FILA_VR01", "sincronizacao": sync,
                "operacao": operation, "erro": type(exc).__name__,
                "envios_realizados": 0, "redmine_escritas": 0}
    return {
        "fila": queue,
        "estado": "INTENCOES_PERSISTIDAS_SEM_ENVIO",
        "sincronizacao": sync,
        "operacao": operation,
        "envios_realizados": 0,
        "redmine_escritas": 0,
    }


if __name__ == "__main__":
    print(json.dumps(executar_ciclo_vr01(), ensure_ascii=False, indent=2, default=str))
