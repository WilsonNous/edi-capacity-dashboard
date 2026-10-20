"""Shared EDDY Redmine read orchestration for multiple independent rules.

Bounded retries are owned by redmine_api. This layer prevents every rule from
re-fetching unchanged journals and makes stale inventory explicit. No SQLite,
external writes, or breaker bypass.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from redmine_api import buscar_chamados_projetos, buscar_detalhes_chamado, obter_diagnostico_redmine
from ednna.mysql_snapshot_repository import carregar_snapshot


def listar_abertos_confirmados() -> dict:
    """Never interpret panel's stale fallback as a fresh Redmine discovery."""
    try:
        issues = buscar_chamados_projetos(
            status_id="open", completar_custom_fields=True, force_refresh=True
        )
        diagnostic = obter_diagnostico_redmine()
        source = diagnostic.get("fonte_dados")
        if not isinstance(issues, list) or source != "redmine":
            return {"confirmado": False, "chamados": [],
                    "motivo": "LISTAGEM_NAO_CONFIRMADA", "fonte": source}
        return {"confirmado": True, "chamados": issues, "fonte": "redmine"}
    except Exception as exc:
        return {"confirmado": False, "chamados": [],
                "motivo": type(exc).__name__, "fonte": "redmine_indisponivel"}


def detalhe_com_retomada(issue: dict, *, force: bool = False) -> dict:
    """Reuse unchanged, journal-complete MySQL snapshot across successive cycles.

    A snapshot can support read-only analysis, but never authorizes an external
    action without a fresh terminal-status preflight and send authorization.
    """
    issue_id = int(issue["id"])
    if not force:
        stored = carregar_snapshot(issue_id)
        if stored:
            row = stored["chamado"]
            payload = row.get("payload_json")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (ValueError, TypeError):
                    payload = None
            updated = issue.get("updated_on")
            stored_updated = row.get("alterado_em")
            # Only snapshots explicitly marked as journal-complete are reusable.
            # The generic panel import writes issue payloads WITHOUT journals.
            complete = isinstance(payload, dict) and payload.get("_eddy_journals_completos") is True
            if updated and stored_updated and complete and isinstance(stored.get("journals"), list):
                try:
                    current_dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                    previous_dt = stored_updated if isinstance(stored_updated, datetime) else datetime.fromisoformat(str(stored_updated).replace("Z", "+00:00"))
                    if current_dt.tzinfo is None:
                        current_dt = current_dt.replace(tzinfo=timezone.utc)
                    if previous_dt.tzinfo is None:
                        previous_dt = previous_dt.replace(tzinfo=timezone.utc)
                    if current_dt.astimezone(timezone.utc) <= previous_dt.astimezone(timezone.utc):
                        restored = dict(payload)
                        restored["journals"] = [
                            {"id": j["id"], "created_on": j.get("criado_em"),
                             "notes": j.get("notas") or "",
                             "details": json.loads(j["detalhes_json"]) if isinstance(j.get("detalhes_json"), str) else (j.get("detalhes_json") or []),
                             "user": {"name": j.get("autor") or ""}}
                            for j in stored["journals"]
                        ]
                        return {"detalhe": restored, "fonte": "mysql_sem_alteracao", "consultou_redmine": False}
                except (ValueError, TypeError, OverflowError):
                    pass
    detail = buscar_detalhes_chamado(issue_id, incluir_journals=True, force_refresh=True)
    if not isinstance(detail, dict) or int(detail.get("id", 0)) != issue_id or not isinstance(detail.get("journals"), list):
        raise ValueError("Detalhe Redmine incompleto")
    return {"detalhe": detail, "fonte": "redmine", "consultou_redmine": True}
