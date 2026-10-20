"""Explicit, read-only Redmine import for VR01 pilot issues."""
from __future__ import annotations
from datetime import datetime, timezone
from redmine_api import buscar_detalhes_chamado
from ednna.mysql_snapshot_repository import salvar_snapshot

ALLOWED_IDS = frozenset({49227, 49289})


def _timestamp(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def importar_chamado_vr(chamado_id: int) -> dict:
    """GET Redmine issue+journals and persist snapshot; no remote writes."""
    if chamado_id not in ALLOWED_IDS:
        raise ValueError("Chamado fora do piloto VR01")
    issue = buscar_detalhes_chamado(chamado_id, incluir_journals=True, force_refresh=True)
    if not issue or int(issue.get("id", 0)) != chamado_id:
        raise ValueError("Resposta Redmine ausente ou com ID divergente")
    if "journals" not in issue or not isinstance(issue["journals"], list):
        raise ValueError("Journals ausentes: importação incompleta")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    subject = issue.get("subject") or ""
    if not any(k in subject.casefold() for k in ("vr beneficio", "vr benefício", "vr beneficios", "vr benefícios")):
        raise ValueError("Chamado não identificado como VR Benefícios")
    row = {
        "id": chamado_id, "cliente": None, "origem": "VR BENEFICIOS",
        "responsavel": (issue.get("assigned_to") or {}).get("name"),
        "projeto": (issue.get("project") or {}).get("name"),
        "tipo": (issue.get("tracker") or {}).get("name"),
        "estado": (issue.get("status") or {}).get("name"),
        "prioridade": (issue.get("priority") or {}).get("name"),
        "assunto": subject, "criado_em": _timestamp(issue.get("created_on")),
        "alterado_em": _timestamp(issue.get("updated_on")),
        "tempo_aberto_dias": None, "payload_json": issue, "sincronizado_em": now,
    }
    journals = []
    for journal in issue["journals"]:
        if journal.get("id") is None:
            raise ValueError("Journal sem ID; importação abortada")
        journals.append({
            "id": int(journal["id"]), "chamado_id": chamado_id,
            "autor": (journal.get("user") or {}).get("name"),
            "criado_em": _timestamp(journal.get("created_on")),
            "notas": journal.get("notes") or "",
            "detalhes_json": journal.get("details") or [],
            "sincronizado_em": now,
        })
    salvar_snapshot(row, journals)
    return {"chamado_id": chamado_id, "journals_importados": len(journals),
            "somente_leitura_redmine": True, "operacao_externa": False}
