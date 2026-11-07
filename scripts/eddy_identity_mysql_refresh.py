"""Low-frequency client identity enrichment; VR01 planning remains MySQL-only.

One pass on startup, then every 30 minutes for unresolved identities. Never sends mail or writes Redmine.
"""
from __future__ import annotations

import json
import os
import time

from ednna.mysql_storage import connect


def executar_uma_vez(limite=20):
    from ednna.eddy_client_identity import resolver_identidade_cliente
    from ednna.eddy_client_identity_store import consultar
    from ednna.eddy_vr_mysql_sync import clientes_do_redmine
    from ednna.eddy_vr_origin import identificar_vr

    # Read from the existing persisted inventory; no Redmine list request.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, cliente, payload_json FROM eddy_chamados
                           WHERE cliente IS NOT NULL AND cliente <> ''
                           ORDER BY alterado_em DESC LIMIT 500""")
            rows = cur.fetchall()
    chosen = {}
    for issue_id, cliente, payload in rows:
        try:
            issue = json.loads(payload) if isinstance(payload, str) else payload
            if (not isinstance(issue, dict) or not identificar_vr(issue)
                    or len(clientes_do_redmine(issue)) != 1):
                continue
            chosen.setdefault(cliente, issue)
        except (TypeError, ValueError):
            continue
    stats = {"clientes": len(chosen), "consultados": 0, "resolvidos": 0,
             "indisponiveis": 0, "sem_bp": 0}
    for cliente, issue in list(chosen.items())[:max(1, min(int(limite), 50))]:
        # Cache-positive identities are reused; missing BP is retried daily,
        # not on every five-minute operational cycle.
        existing = consultar(cliente)
        if existing and existing["estado"] == "RESOLVIDO":
            continue
        result = resolver_identidade_cliente(
            issue, allow_remote=True, cliente_override=cliente)
        stats["consultados"] += 1
        if result["estado"] == "RESOLVIDO":
            stats["resolvidos"] += 1
        elif result["estado"] in ("FONTE_BP_INDISPONIVEL", "IDENTIDADE_MYSQL_INDISPONIVEL"):
            stats["indisponiveis"] += 1
            # Do not flood Redmine during circuit-breaker incidents.
            break
        else:
            stats["sem_bp"] += 1
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
