"""VR01 original-owner contract. No Redmine writes or external effects."""
from __future__ import annotations


def capturar_responsavel_original(issue: dict, automation_user_id: int) -> dict:
    """Capture verified owner before automation takes assignment; fail closed."""
    if not isinstance(issue, dict) or type(issue.get("id")) is not int:
        raise ValueError("CHAMADO_INVALIDO")
    assignee = issue.get("assigned_to")
    if not isinstance(assignee, dict) or type(assignee.get("id")) is not int:
        raise ValueError("RESPONSAVEL_NAO_CONFIRMADO")
    owner_id = assignee["id"]
    if owner_id <= 0 or owner_id == automation_user_id:
        raise ValueError("RESPONSAVEL_ORIGINAL_NAO_RECUPERAVEL")
    version = str(issue.get("updated_on") or "").strip()
    if not version:
        raise ValueError("VERSAO_REDMINE_AUSENTE")
    return {"chamado_id": issue["id"], "original_owner_id": owner_id,
            "original_owner_name": str(assignee.get("name") or ""),
            "captured_updated_on": version}


def verificar_devolucao(issue: dict, ownership: dict) -> dict:
    """Verify fresh Redmine assignment equals captured original owner."""
    if not isinstance(issue, dict) or not isinstance(ownership, dict):
        return {"confirmado": False, "motivo": "EVIDENCIA_AUSENTE"}
    if issue.get("id") != ownership.get("chamado_id"):
        return {"confirmado": False, "motivo": "CHAMADO_DIVERGENTE"}
    assignee = issue.get("assigned_to")
    if not isinstance(assignee, dict) or type(ownership.get("original_owner_id")) is not int:
        return {"confirmado": False, "motivo": "RESPONSAVEL_INVALIDO"}
    if assignee.get("id") != ownership["original_owner_id"]:
        return {"confirmado": False, "motivo": "DEVOLUCAO_NAO_CONFIRMADA"}
    if not issue.get("updated_on"):
        return {"confirmado": False, "motivo": "VERSAO_AUSENTE"}
    return {"confirmado": True, "motivo": "RESPONSAVEL_ORIGINAL_RESTAURADO"}


def recuperar_responsavel_por_journals(issue: dict, journals: list, automation_user_id: int) -> int | None:
    """Recover the human owner immediately before EDDY took assignment.

    Requires a journal-complete snapshot and a current EDDY assignment.
    A historical assignee elsewhere in the timeline is not sufficient.
    This function is read-only and deliberately refuses ambiguous evidence.
    """
    if (not isinstance(issue, dict) or issue.get("_eddy_journals_completos") is not True
            or not isinstance(journals, list) or type(automation_user_id) is not int
            or automation_user_id <= 0):
        return None
    assignee = issue.get("assigned_to") or {}
    if not isinstance(assignee, dict) or assignee.get("id") != automation_user_id:
        return None
    transitions = []
    for journal in journals:
        if not isinstance(journal, dict) or type(journal.get("id")) is not int:
            return None
        details = journal.get("detalhes_json", journal.get("details", []))
        if isinstance(details, str):
            import json
            try:
                details = json.loads(details)
            except (TypeError, ValueError):
                return None
        if not isinstance(details, list):
            return None
        for detail in details:
            if not isinstance(detail, dict):
                return None
            if (detail.get("property") == "attr"
                    and str(detail.get("name")) == "assigned_to_id"):
                transitions.append((journal["id"], detail))
    if not transitions:
        return None
    transitions.sort(key=lambda pair: pair[0])
    last = transitions[-1][1]
    try:
        new_id = int(last.get("new_value"))
        old_id = int(last.get("old_value"))
    except (TypeError, ValueError):
        return None
    if new_id != automation_user_id or old_id <= 0 or old_id == automation_user_id:
        return None
    return old_id
