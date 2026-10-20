"""Read-only VR01 operation projection sourced exclusively from MySQL.

No SQLite fallback and no external effects. Fail closed if MySQL is unavailable.
"""
from __future__ import annotations

from ednna.mysql_storage import connect
from ednna.mysql_snapshot_repository import CHAMADO_FIELDS, JOURNAL_FIELDS
from ednna.eddy_vr_rule import avaliar_vr
from ednna.eddy_vr_followup import planejar_followup
from ednna.eddy_vr_observability import resumir_operacao_vr
from ednna.eddy_vr_origin import identificar_vr


def operacao_vr_mysql() -> dict:
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT " + ", ".join(CHAMADO_FIELDS)
                + " FROM eddy_chamados ORDER BY id"
            )
            chamados = [dict(zip(CHAMADO_FIELDS, row)) for row in cursor.fetchall()]
            results = []
            vr_count = 0
            for chamado in chamados:
                if not identificar_vr(chamado):
                    continue
                vr_count += 1
                cursor.execute(
                    "SELECT " + ", ".join(JOURNAL_FIELDS)
                    + " FROM eddy_journals WHERE chamado_id=%s ORDER BY id",
                    (chamado["id"],)
                )
                journals = [dict(zip(JOURNAL_FIELDS, row)) for row in cursor.fetchall()]
                decision = avaliar_vr(chamado, journals)
                followup = planejar_followup(decision, journals)
                results.append({
                    "chamado_id": chamado["id"],
                    "fase_eddy": decision.get("estado"),
                    "proxima_acao": decision.get("acao"),
                    "followup": followup.get("situacao"),
                    "vencimento": followup.get("vencimento"),
                    "evidencia_envio_confirmada": followup.get("situacao") in (
                        "AGUARDANDO_PRAZO", "FOLLOWUP_VENCIDO", "RESPOSTA_RECEBIDA"
                    ),
                })
    projection = resumir_operacao_vr({
        "somente_leitura": True, "chamados": results, "falhas": []
    })
    projection["fonte"] = "mysql"
    projection["total_snapshots_vr"] = vr_count
    projection["aviso"] = (
        "Somente snapshots já sincronizados no MySQL; não garante cobertura "
        "de todos os chamados abertos no Redmine."
    )
    return projection
