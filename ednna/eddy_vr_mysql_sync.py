"""Synchronize all currently open VR01 issues from Redmine to MySQL.

No email sends, no Redmine writes, no SQLite. A failed detail is not persisted.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ednna.mysql_snapshot_repository import salvar_snapshot
from ednna.redmine_resilient_reads import listar_abertos_confirmados, detalhe_com_retomada
from scripts.eddy_vr01_open_inventory import _is_vr


def _timestamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _snapshot(issue: dict, now: datetime) -> tuple[dict, list[dict]]:
    issue_id = int(issue["id"])
    if not isinstance(issue.get("journals"), list):
        raise ValueError("Histórico Redmine incompleto")
    if not _is_vr(issue):
        raise ValueError("Detalhe não corresponde à regra VR")
    status = (issue.get("status") or {}).get("name")
    if not status:
        raise ValueError("Status Redmine ausente")
    row = {
        "id": issue_id, "cliente": None, "origem": next((str(f.get("value")) for f in issue.get("custom_fields", []) if str(f.get("id")) == "5" and f.get("value") not in (None, "")), "VR BENEFICIOS"),
        "responsavel": (issue.get("assigned_to") or {}).get("name"),
        "projeto": (issue.get("project") or {}).get("name"),
        "tipo": (issue.get("tracker") or {}).get("name"),
        "estado": status,
        "prioridade": (issue.get("priority") or {}).get("name"),
        "assunto": issue.get("subject"),
        "criado_em": _timestamp(issue.get("created_on")),
        "alterado_em": _timestamp(issue.get("updated_on")),
        "tempo_aberto_dias": None,
        "payload_json": issue, "sincronizado_em": now,
    }
    journals = []
    for journal in issue["journals"]:
        if journal.get("id") is None:
            raise ValueError("Journal sem ID")
        journals.append({
            "id": int(journal["id"]), "chamado_id": issue_id,
            "autor": (journal.get("user") or {}).get("name"),
            "criado_em": _timestamp(journal.get("created_on")),
            "notas": journal.get("notes") or "",
            "detalhes_json": journal.get("details") or [],
            "sincronizado_em": now,
        })
    return row, journals


def sincronizar_carteira_vr_mysql() -> dict:
    inventario = listar_abertos_confirmados()
    if not inventario["confirmado"]:
        return {"fonte": inventario.get("fonte"), "destino": "mysql",
                "abertos_consultados": 0, "vr_identificados": 0,
                "importados": [], "reutilizados_mysql": [], "falhas": [],
                "cobertura_completa": False, "motivo": inventario.get("motivo"),
                "redmine_somente_leitura": True, "envios_realizados": 0}
    issues = inventario["chamados"]
    candidates = [item for item in issues if _is_vr(item)]
    imported, reused, failures = [], [], []
    for item in sorted(candidates, key=lambda x: int(x["id"])):
        issue_id = int(item["id"])
        try:
            leitura = detalhe_com_retomada(item)
            detail = leitura["detalhe"]
            if not isinstance(detail, dict) or int(detail.get("id", 0)) != issue_id:
                raise ValueError("Detalhe Redmine ausente ou divergente")
            row, journals = _snapshot(detail, datetime.now(timezone.utc).replace(tzinfo=None))
            if leitura["consultou_redmine"]:
                salvar_snapshot(row, journals)
                imported.append(issue_id)
            else:
                reused.append(issue_id)
        except Exception as exc:
            failures.append({"chamado_id": issue_id, "erro": type(exc).__name__})
    return {
        "fonte": "redmine", "destino": "mysql", "abertos_consultados": len(issues),
        "vr_identificados": len(candidates), "importados": imported,
        "reutilizados_mysql": reused,
        "falhas": failures, "cobertura_completa": len(failures) == 0 and len(candidates) > 0,
        "redmine_somente_leitura": True, "envios_realizados": 0,
    }
