"""Read-only gate before retiring legacy EDNNA SQLite.

Never deletes source files or modifies Redmine.
"""
from __future__ import annotations

import json

from ednna.mysql_storage import connect


def verificar():
    required = ("eddy_chamados", "eddy_journals",
                "eddy_redmine_field_definitions", "eddy_redmine_field_options",
                "eddy_blueprint_participants")
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db = cursor.fetchone()[0]
            cursor.execute("SHOW TABLES")
            available = {row[0] for row in cursor.fetchall()}
            counts = {}
            for name in required:
                if name in available:
                    cursor.execute("SELECT COUNT(*) FROM " + name)
                    counts[name] = int(cursor.fetchone()[0])
    missing = sorted(set(required) - available)
    blockers = []
    if missing:
        blockers.append("TABELAS_AUSENTES")
    for name in ("eddy_redmine_field_definitions", "eddy_redmine_field_options"):
        if counts.get(name, 0) == 0:
            blockers.append("CATALOGO_NAO_SINCRONIZADO")
            break
    if counts.get("eddy_blueprint_participants", 0) == 0:
        blockers.append("PARTICIPANTES_BLUEPRINT_NAO_MIGRADOS")
    # A full cutover additionally needs source-to-target reconciliation of
    # operational memory, workflow tables, and verified Azure deployment.
    blockers.append("RECONCILIACAO_INTEGRAL_PENDENTE")
    return {"modo": "SOMENTE_LEITURA", "mysql_database": db,
            "tabelas_ausentes": missing, "contagens": counts,
            "cutover_autorizado": False, "bloqueios": blockers,
            "sqlite_removido": False, "envios_realizados": 0,
            "redmine_escritas": 0, "mysql_escritas": 0}


if __name__ == "__main__":
    print(json.dumps(verificar(), ensure_ascii=False))
