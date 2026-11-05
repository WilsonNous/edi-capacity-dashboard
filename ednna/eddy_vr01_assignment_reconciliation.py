"""Read-only evidence and reconciliation report for MAMBO VR01 assignment.

Never performs a Redmine PUT, changes a lifecycle row, creates tables, or
changes readiness flags. A pending reservation is never cleared automatically.
"""
from __future__ import annotations

from ednna.eddy_vr01_integrated import (
    ISSUE_ID, ORIGINAL_OWNER_ID, _assignee, _identity, _read_issue,
)
from ednna.mysql_storage import connect

_LEDGER_SQL = """SELECT fase, original_owner_id, eddy_owner_id,
    operacao_pendente FROM eddy_vr01_lifecycle_audit WHERE chamado_id=%s"""
_EVENTS_SQL = """SELECT evento, referencia FROM eddy_vr01_lifecycle_events
    WHERE chamado_id=%s AND evento='ASSUNCAO_EDDY' ORDER BY id"""


def diagnosticar_reconciliacao_assuncao() -> dict:
    """Inspect actual Redmine assignment and MySQL audit without any writes."""
    report = {
        "chamado_id": ISSUE_ID, "operacao": "ASSUMIR_REDMINE",
        "modo": "SOMENTE_LEITURA", "execucao_externa": False,
        "reconciliado": False, "bloqueios": [],
    }
    try:
        eddy_id = _identity()
        report["eddy_user_id"] = eddy_id
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_LEDGER_SQL, (ISSUE_ID,))
                row = cur.fetchone()
                if row is None:
                    report["bloqueios"].append("LEDGER_AUSENTE")
                    return report
                phase, original_id, ledger_eddy_id, pending = row
                cur.execute(_EVENTS_SQL, (ISSUE_ID,))
                events = cur.fetchall()
        report.update({
            "fase_mysql": phase,
            "operacao_pendente": pending,
            "eventos_assuncao": len(events),
        })
        if original_id != ORIGINAL_OWNER_ID or ledger_eddy_id != eddy_id:
            report["bloqueios"].append("IDENTIDADE_LEDGER_DIVERGENTE")
            return report
        issue = _read_issue(ISSUE_ID)
        assignee = _assignee(issue)
        report["responsavel_redmine_id"] = assignee
        report["redmine_updated_on"] = issue.get("updated_on")
        if not issue.get("updated_on"):
            report["bloqueios"].append("VERSAO_REDMINE_AUSENTE")
        if pending:
            report["bloqueios"].append("OPERACAO_PENDENTE_RECONCILIACAO_MANUAL")
        confirmed_event = any(name == "ASSUNCAO_EDDY" and
                              str(ref) == str(eddy_id) for name, ref in events)
        if phase == "ASSUMIDO_EDDY" and assignee == eddy_id and confirmed_event and not pending:
            report["reconciliado"] = not report["bloqueios"]
            report["situacao"] = "ASSUNCAO_CONFIRMADA" if report["reconciliado"] else "VERIFICAR_MANUALMENTE"
        elif phase == "PRONTO_PARA_ASSUMIR" and assignee == ORIGINAL_OWNER_ID and not pending and not events:
            report["situacao"] = "AGUARDA_ASSUNCAO_AUTORIZADA"
        elif assignee == eddy_id and pending:
            report["situacao"] = "REDMINE_ATRIBUIDO_MYSQL_PENDENTE"
        else:
            report["situacao"] = "DIVERGENCIA_REQUER_ANALISE_MANUAL"
        if report["situacao"] in ("REDMINE_ATRIBUIDO_MYSQL_PENDENTE",
                                  "DIVERGENCIA_REQUER_ANALISE_MANUAL"):
            report["bloqueios"].append("RECONCILIACAO_MANUAL_NECESSARIA")
    except Exception as exc:
        report["bloqueios"].append("FALHA_DIAGNOSTICO_" + type(exc).__name__)
        report["situacao"] = "DIAGNOSTICO_INCOMPLETO"
    return report
