"""Non-destructive MySQL homologation for EDDY operational actions.

Run only against a dedicated, disposable homologation schema, never production.
No Graph, Redmine, email, or external automation is invoked.
"""
from __future__ import annotations

import os
import uuid

from ednna import acompanhamento_acoes as actions
from ednna.mysql_storage import connect, storage_health


def main():
    if os.getenv("EDDY_MYSQL_HOMOLOGATION") != "1":
        raise SystemExit("Set EDDY_MYSQL_HOMOLOGATION=1 explicitly")
    if os.getenv("EDDY_DB_ENGINE") != "mysql":
        raise SystemExit("EDDY_DB_ENGINE=mysql required")
    dbname = os.getenv("EDDY_DB_NAME", "")
    if not dbname.endswith("_homolog"):
        raise SystemExit("Dedicated MySQL schema ending _homolog required")
    rule = "HOMOLOG_" + uuid.uuid4().hex[:12]
    issue = 900000000 + (uuid.uuid4().int % 90000000)
    actions.inicializar_acompanhamento()
    first, row = actions.adquirir_envio(issue, rule)
    assert first and row["estado"] == "ENVIANDO", "initial acquisition failed"
    second, _ = actions.adquirir_envio(issue, rule)
    assert not second, "duplicate acquisition was accepted"
    confirmed = actions.confirmar_envio_real(
        issue, rule, email_assunto="HOMOLOGACAO SEM ENVIO",
        graph_message_id="synthetic-homolog-" + uuid.uuid4().hex,
    )
    assert confirmed["envio_confirmado"] == 1, "confirmation not persisted"
    third, _ = actions.adquirir_envio(issue, rule)
    assert not third, "confirmed send was reacquired"
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT estado, envio_confirmado FROM eddy_acoes_operacionais
                              WHERE chamado_id=%s AND regra_id=%s""", (issue, rule))
            state = cursor.fetchone()
    assert state == ("AGUARDANDO_RESPOSTA", 1), "database state differs"
    print("[HOMOLOG] MySQL acquisition, deduplication, confirmation and readback: PASS")
    print("[HOMOLOG] Storage:", storage_health())
    print("[HOMOLOG] Synthetic record retained for audit:", issue, rule)


if __name__ == "__main__":
    main()
