"""Read-only full VR01 assessment: discovery, classification and follow-up evidence gaps."""
from __future__ import annotations

import json

from ednna.eddy_vr_rule import avaliar_vr
from ednna.eddy_vr_followup import planejar_followup
from scripts.eddy_vr01_open_inventory import _is_vr
from redmine_api import buscar_chamados_projetos, buscar_detalhes_chamado


def avaliar_carteira_vr() -> dict:
    """No MySQL/Redmine writes or outgoing communication. Fail closed on missing history."""
    open_issues = buscar_chamados_projetos(
        status_id="open", completar_custom_fields=True, force_refresh=True
    )
    if not isinstance(open_issues, list):
        raise ValueError("Listagem Redmine inválida")
    vr = [item for item in open_issues if _is_vr(item)]
    results, failures = [], []
    for item in sorted(vr, key=lambda issue: int(issue["id"])):
        issue_id = int(item["id"])
        try:
            detail = buscar_detalhes_chamado(
                issue_id, incluir_journals=True, force_refresh=True
            )
            if not isinstance(detail, dict) or int(detail.get("id", 0)) != issue_id:
                raise ValueError("Detalhe inválido")
            journals = detail.get("journals")
            if not isinstance(journals, list):
                raise ValueError("Histórico Redmine incompleto")
            status = (detail.get("status") or {}).get("name", "")
            # Explicit current status and full payload; do not trust stale list row.
            snapshot = {
                "id": issue_id, "origem": "VR BENEFICIOS",
                "estado": status, "payload_json": detail
            }
            decision = avaliar_vr(snapshot, journals)
            followup = planejar_followup(decision, journals)
            results.append({
                "chamado_id": issue_id, "estado_redmine": status,
                "fase_eddy": decision.get("estado"),
                "proxima_acao": decision.get("acao"),
                "followup": followup.get("situacao"),
                "vencimento": followup.get("vencimento"),
                "evidencia_envio_confirmada": followup.get("situacao")
                    in ("AGUARDANDO_PRAZO", "FOLLOWUP_VENCIDO", "RESPOSTA_RECEBIDA"),
                "execucao_externa": False,
            })
        except Exception as exc:
            failures.append({"chamado_id": issue_id, "erro": type(exc).__name__})
    return {
        "abertos_consultados": len(open_issues),
        "vr_identificados": len(vr),
        "avaliados": len(results),
        "falhas": failures,
        "chamados": results,
        "somente_leitura": True,
        "observacao": "Journals Redmine não comprovam envio sem evidência verificada.",
    }


if __name__ == "__main__":
    print(json.dumps(avaliar_carteira_vr(), ensure_ascii=False, indent=2))
