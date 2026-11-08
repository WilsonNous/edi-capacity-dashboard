"""Global, bounded Blueprint enrichment: Redmine sources, MySQL persistence.

Rotates through all known clients across cycles; never sends mail or writes Redmine.
"""
from __future__ import annotations

import json
import os
import time

from ednna.mysql_storage import connect

CURSOR_DDL = """CREATE TABLE IF NOT EXISTS eddy_blueprint_refresh_cursor (
    worker VARCHAR(64) NOT NULL PRIMARY KEY,
    last_cliente VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def _inventario():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, cliente, payload_json FROM eddy_chamados
                           WHERE cliente IS NOT NULL AND cliente <> ''
                           ORDER BY alterado_em DESC""")
            rows = cur.fetchall()
    chosen = {}
    for issue_id, cliente, payload in rows:
        try:
            issue = json.loads(payload) if isinstance(payload, str) else payload
            if not isinstance(issue, dict) or int(issue.get("id") or 0) != int(issue_id):
                continue
            chosen.setdefault(str(cliente).strip(), issue)
        except (TypeError, ValueError):
            continue
    return chosen


def _lote(chosen, limite):
    """Durable cursor: failure in one cycle cannot starve the other clients."""
    names = sorted(chosen)
    if not names:
        return []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(CURSOR_DDL)
            cur.execute("SELECT last_cliente FROM eddy_blueprint_refresh_cursor WHERE worker=%s",
                        ("GLOBAL_BP",))
            row = cur.fetchone()
            last = str(row[0]) if row else ""
            start = next((i for i, name in enumerate(names) if name > last), 0)
            batch = [names[(start + i) % len(names)]
                     for i in range(min(len(names), max(1, min(int(limite), 100))))]
    return [(name, chosen[name]) for name in batch]


def _confirmar_progresso(cliente):
    """Advance cursor only after completing the client refresh."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(CURSOR_DDL)
            cur.execute("""INSERT INTO eddy_blueprint_refresh_cursor (worker, last_cliente)
                           VALUES (%s,%s) ON DUPLICATE KEY UPDATE last_cliente=VALUES(last_cliente)""",
                        ("GLOBAL_BP", cliente))


def executar_uma_vez(limite=20):
    from ednna.eddy_client_identity import resolver_identidade_cliente
    from ednna.mysql_blueprint_participants import descobrir_e_sincronizar_participantes_mysql
    chosen = _inventario()
    batch = _lote(chosen, limite)
    stats = {"clientes": len(chosen), "selecionados": len(batch), "bp_sincronizados": 0,
             "consultados": 0, "resolvidos": 0, "indisponiveis": 0,
             "sem_bp": 0, "sem_blueprint": 0, "falhas_descoberta": 0,
             "falhas_anexo": 0, "interrompido_por_redmine": False}
    for cliente, issue in batch:
        discovery = descobrir_e_sincronizar_participantes_mysql(
            {int(issue["id"]): cliente}, aplicar=True, skip_imported=False)
        statuses = [row.get("status") for row in discovery.get("resultados", [])]
        contexts = [row.get("status") for row in discovery.get("descoberta", [])]
        stats["bp_sincronizados"] += statuses.count("IMPORTADO")
        stats["sem_blueprint"] += contexts.count("BLUEPRINT_NAO_LOCALIZADO")
        stats["falhas_descoberta"] += contexts.count("CONTEXTO_INDISPONIVEL")
        stats["falhas_anexo"] += statuses.count("ERRO_ANEXO") + statuses.count("ERRO_CHAMADO")
        # Avoid a second Redmine relation walk if the first has already failed.
        if "CONTEXTO_INDISPONIVEL" in contexts:
            stats["indisponiveis"] += 1
            stats["interrompido_por_redmine"] = True
            break
        result = resolver_identidade_cliente(
            issue, allow_remote=False, cliente_override=cliente, refresh_mysql=True)
        stats["consultados"] += 1
        if result["estado"] == "RESOLVIDO":
            stats["resolvidos"] += 1
        elif result["estado"] == "IDENTIDADE_MYSQL_INDISPONIVEL":
            stats["indisponiveis"] += 1
            break
        else:
            stats["sem_bp"] += 1
        _confirmar_progresso(cliente)
    return stats


def main():
    interval = max(1800, int(os.getenv("EDDY_IDENTITY_REFRESH_INTERVAL_SECONDS", "1800")))
    while True:
        try:
            print("[EDDY-IDENTIDADE-MYSQL] " +
                  json.dumps(executar_uma_vez(), ensure_ascii=False), flush=True)
        except Exception as exc:
            print("[EDDY-IDENTIDADE-MYSQL] falha=" + type(exc).__name__, flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
