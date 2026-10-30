"""Read-only VR01 operation projection sourced exclusively from MySQL.

No SQLite fallback and no external effects. Fail closed if MySQL is unavailable.
"""
from __future__ import annotations
import json


def _prazo_redmine(chamado):
    payload = chamado.get('payload_json') or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            payload = {}
    if not isinstance(payload, dict):
        return None
    return payload.get('due_date') or None


from ednna.mysql_storage import connect
from ednna.mysql_snapshot_repository import CHAMADO_FIELDS, JOURNAL_FIELDS
from ednna.eddy_vr_rule import avaliar_vr
from ednna.eddy_vr_continuity import decidir_continuidade_vr
from ednna.eddy_vr_followup import planejar_followup
from ednna.eddy_vr_observability import resumir_operacao_vr
from ednna.eddy_vr_origin import identificar_vr


def _snapshot_elegivel(chamado: dict) -> bool:
    """Do not promote historical or journal-incomplete issues into VR queues."""
    payload = chamado.get("payload_json") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (ValueError, TypeError):
            return False
    if not isinstance(payload, dict) or payload.get("_eddy_journals_completos") is not True:
        return False
    status = payload.get("status") or {}
    if not isinstance(status, dict):
        return False
    if status.get("is_closed") is True:
        return False
    state = str(status.get("name") or chamado.get("estado") or "").casefold()
    return bool(state) and not any(
        word in state for word in ("concluído", "concluido", "fechado", "rejeitado", "closed", "cancelado")
    )


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
                if not _snapshot_elegivel(chamado):
                    continue
                cursor.execute(
                    "SELECT " + ", ".join(JOURNAL_FIELDS)
                    + " FROM eddy_journals WHERE chamado_id=%s ORDER BY id",
                    (chamado["id"],)
                )
                journals = [dict(zip(JOURNAL_FIELDS, row)) for row in cursor.fetchall()]
                # Redmine evaluator expects original journal notes and timestamp names.
                journals = [{**j, "notes": j.get("notas") or "",
                             "created_on": j.get("criado_em")} for j in journals]
                decision = avaliar_vr(chamado, journals)
                payload = chamado.get('payload_json') or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)
                continuidade = decidir_continuidade_vr(payload, journals) if isinstance(payload, dict) else {}
                followup = planejar_followup(decision, journals)
                results.append({
                    "chamado_id": chamado["id"],
                    "etapa_continuidade": continuidade.get("etapa"),
                    "acao_continuidade": continuidade.get("acao"),
                    "destino_continuidade": continuidade.get("destino"),
                    "fase_eddy": decision.get("estado"),
                    "proxima_acao": decision.get("acao"),
                    "followup": followup.get("situacao"),
                    "vencimento": followup.get("vencimento"),
                    "prazo_chamado": _prazo_redmine(chamado),
                    "evidencia_envio_confirmada": followup.get("situacao") in (
                        "AGUARDANDO_PRAZO", "FOLLOWUP_VENCIDO", "RESPOSTA_RECEBIDA"
                    ),
                })
    projection = resumir_operacao_vr({
        "somente_leitura": True, "chamados": results, "falhas": []
    })
    projection["fonte"] = "mysql"
    projection["total_snapshots_vr"] = vr_count
    projection["snapshots_elegiveis"] = len(results)
    projection["snapshots_sem_historico_completo_ou_terminais"] = vr_count - len(results)
    projection["aviso"] = (
        "Somente snapshots já sincronizados no MySQL; não garante cobertura "
        "de todos os chamados abertos no Redmine."
    )
    return projection
