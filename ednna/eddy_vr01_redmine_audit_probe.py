"""Read-only VR01 Redmine/MySQL audit homologation probe.

This checks structural prerequisites; it cannot prove Redmine PUT capability,
and deliberately never changes readiness flags or writes to customer systems.
"""
from __future__ import annotations

from ednna.eddy_vr01_integrated import (
    ISSUE_ID, ORIGINAL_OWNER_ID, _assignee, _identity, _load, _read_issue,
)
from ednna.mysql_storage import connect


def diagnosticar_auditoria_assuncao() -> dict:
    report = {"chamado_id": ISSUE_ID, "operacao": "ASSUMIR_REDMINE",
              "modo": "SOMENTE_LEITURA", "homologado": False,
              "execucao_externa": False, "verificacoes": {}, "bloqueios": []}
    try:
        identity = _identity()
        row = _load()
        report["verificacoes"]["ledger_existente"] = row is not None
        if row is None:
            report["bloqueios"].append("LEDGER_AUSENTE")
            return report
        report["verificacoes"]["identidade_ledger"] = (
            row.get("original_owner_id") == ORIGINAL_OWNER_ID
            and row.get("eddy_owner_id") == identity
        )
        if not report["verificacoes"]["identidade_ledger"]:
            report["bloqueios"].append("IDENTIDADE_DIVERGENTE")
            return report
        report["verificacoes"]["fase_inicial"] = row.get("fase") == "PRONTO_PARA_ASSUMIR"
        report["verificacoes"]["sem_operacao_pendente"] = not row.get("operacao_pendente")
        if not report["verificacoes"]["fase_inicial"]:
            report["bloqueios"].append("FASE_NAO_INICIAL")
        if not report["verificacoes"]["sem_operacao_pendente"]:
            report["bloqueios"].append("RECONCILIACAO_PENDENTE")
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM eddy_vr01_lifecycle_events WHERE chamado_id=%s",
                            (ISSUE_ID,))
                count = int(cur.fetchone()[0])
        report["verificacoes"]["leitura_eventos_mysql"] = True
        report["quantidade_eventos"] = count
        issue = _read_issue(ISSUE_ID)
        report["verificacoes"]["redmine_preflight"] = True
        report["verificacoes"]["versao_redmine"] = bool(issue.get("updated_on"))
        report["verificacoes"]["responsavel_original"] = _assignee(issue) == ORIGINAL_OWNER_ID
        if not report["verificacoes"]["versao_redmine"]:
            report["bloqueios"].append("VERSAO_REDMINE_AUSENTE")
        if not report["verificacoes"]["responsavel_original"]:
            report["bloqueios"].append("RESPONSAVEL_ATUAL_DIVERGENTE")
    except Exception as exc:
        report["bloqueios"].append("FALHA_PROBE_" + type(exc).__name__)
    # A successful read-only probe is NOT a write/audit homologation.
    report["preflight_apto"] = not report["bloqueios"]
    report["bloqueios"].append("TESTE_ESCRITA_E_RECONCILIACAO_NAO_HOMOLOGADO")
    return report
