"""Read-only inventory of open VR Beneficios issues, independent of EDNNA."""
from __future__ import annotations

import json
from redmine_api import buscar_chamados_projetos, buscar_detalhes_chamado, traduzir_custom_field

VR_NAMES = ("vr beneficio", "vr benefícios", "vr beneficios", "vr benefício")


def _is_vr(issue: dict) -> bool:
    values = [issue.get("subject") or ""]
    for field in issue.get("custom_fields") or []:
        if field.get("id") == 5:
            raw = field.get("value")
            values.append(str(raw or ""))
            try:
                values.append(str(traduzir_custom_field(raw, 5) or ""))
            except (ValueError, TypeError, KeyError):
                pass
    return any(name in " ".join(values).casefold() for name in VR_NAMES)


def inventariar_vr_abertos(*, limite_detalhes: int | None = None) -> dict:
    """Discover all open issues and inspect candidates; no Redmine writes."""
    issues = buscar_chamados_projetos(
        status_id="open", completar_custom_fields=True, force_refresh=True
    )
    if not isinstance(issues, list):
        raise ValueError("Listagem Redmine inválida")
    candidates = [issue for issue in issues if _is_vr(issue)]
    candidates.sort(key=lambda issue: int(issue["id"]))
    if limite_detalhes is not None:
        candidates = candidates[:limite_detalhes]
    result = []
    errors = []
    for item in candidates:
        issue_id = int(item["id"])
        try:
            detail = buscar_detalhes_chamado(
                issue_id, incluir_journals=True, force_refresh=True
            )
            if not detail or int(detail.get("id", 0)) != issue_id:
                raise ValueError("Detalhe ausente ou ID divergente")
            if "journals" not in detail:
                raise ValueError("Histórico incompleto")
            result.append({"chamado_id": issue_id,
                           "assunto": detail.get("subject"),
                           "estado": (detail.get("status") or {}).get("name"),
                           "journals": len(detail["journals"]),
                           "resultado": "PRONTO_PARA_AVALIACAO"})
        except Exception as exc:
            errors.append({"chamado_id": issue_id, "erro": type(exc).__name__})
    return {"total_abertos_consultados": len(issues),
            "candidatos_vr_encontrados": len([x for x in issues if _is_vr(x)]),
            "candidatos_inspecionados": len(candidates),
            "detalhes_validos": result, "falhas": errors,
            "somente_leitura": True}


def main():
    print(json.dumps(inventariar_vr_abertos(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
