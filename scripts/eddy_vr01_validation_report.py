"""Read-only VR01 pilot validation report from durable MySQL records.

No Redmine/Graph access, external execution, DDL or writes. Do not log notes,
email addresses, destinations, or full issue payloads.
"""
from __future__ import annotations

import json

from ednna.eddy_vr01_offline_proposals import PILOT_IDS
from ednna.eddy_vr_action_queue import criar_intencao
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.mysql_storage import connect


def validar_pilotos(ids=PILOT_IDS) -> dict:
    """Reconcile each current snapshot with the durable queue, without mutations."""
    results = []
    with connect() as conn:
        with conn.cursor() as cursor:
            for issue_id in ids:
                item = {"chamado_id": issue_id, "aprovado_para_envio": False}
                stored = carregar_snapshot(issue_id)
                if not stored:
                    item["estado"] = "SNAPSHOT_AUSENTE"
                    results.append(item)
                    continue
                raw = stored["chamado"].get("payload_json")
                try:
                    issue = json.loads(raw) if isinstance(raw, str) else raw
                except (ValueError, TypeError):
                    issue = None
                if not isinstance(issue, dict) or issue.get("id") != issue_id:
                    item["estado"] = "SNAPSHOT_INVALIDO"
                    results.append(item)
                    continue
                journals = [
                    {"notes": row.get("notas") or "", "created_on": row.get("criado_em")}
                    for row in stored.get("journals", [])
                ]
                proposal = criar_intencao(issue, journals)
                item.update({
                    "versao_redmine": str(issue.get("updated_on") or ""),
                    "historico_completo": issue.get("_eddy_journals_completos") is True,
                    "journals_contados": len(journals),
                    "decisao": proposal.get("situacao"),
                })
                if proposal.get("situacao") != "PENDENTE":
                    item["estado"] = "SEM_PROPOSTA_VALIDA"
                    results.append(item)
                    continue
                item.update({
                    "etapa": proposal["etapa"],
                    "acao": proposal["acao"],
                    "destino_definido": bool(proposal.get("destino")),
                })
                cursor.execute(
                    """SELECT action_key, redmine_updated_on, etapa, acao, situacao
                       FROM eddy_vr01_action_queue
                       WHERE chamado_id=%s AND action_key=%s""",
                    (issue_id, proposal["action_key"]),
                )
                row = cursor.fetchone()
                if row is None:
                    item["estado"] = "PROPOSTA_NAO_PERSISTIDA"
                else:
                    key, version, stage, action, status = row
                    item["situacao_persistida"] = status
                    item["versao_coincide"] = version == proposal["redmine_updated_on"]
                    item["decisao_coincide"] = stage == proposal["etapa"] and action == proposal["acao"]
                    item["estado"] = (
                        "PROPOSTA_OBSERVACIONAL_CONFERIDA"
                        if key == proposal["action_key"] and status == "OBSERVACIONAL"
                        and item["versao_coincide"] and item["decisao_coincide"]
                        else "PROPOSTA_DIVERGENTE_OU_NAO_OBSERVACIONAL"
                    )
                results.append(item)
    return {
        "modo": "SOMENTE_LEITURA",
        "avaliados": len(results),
        "conferidos": sum(x["estado"] == "PROPOSTA_OBSERVACIONAL_CONFERIDA" for x in results),
        "envios_realizados": 0,
        "redmine_escritas": 0,
        "homologacao_externa": False,
        "chamados": results,
    }


def main() -> None:
    print(json.dumps(validar_pilotos(), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
