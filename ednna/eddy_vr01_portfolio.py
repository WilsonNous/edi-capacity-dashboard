"""Portfolio VR01 coordinator: per-issue lifecycle readiness without pilot constants.

This module does not dispatch Graph messages or mutate Redmine. It produces
per-issue execution plans and exposes the exact blockers for operational rollout.
"""
from __future__ import annotations

import json
from ednna.eddy_vr_origin import identificar_vr
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.eddy_vr01_offline_proposals import listar_chamados_vr_mysql
from ednna.eddy_vr_action_queue import criar_intencao
from ednna.eddy_vr_mysql_sync import clientes_do_redmine


def planejar_carteira_vr01(ids=None) -> dict:
    selected = tuple(dict.fromkeys(int(i) for i in (
        listar_chamados_vr_mysql() if ids is None else ids
    )))
    result = []
    for issue_id in selected:
        entry = {"chamado_id": issue_id, "execucao_externa": False}
        try:
            snapshot = carregar_snapshot(issue_id)
            if not snapshot:
                entry.update(estado="BLOQUEADO_SNAPSHOT_AUSENTE")
            else:
                payload = snapshot["chamado"].get("payload_json") or {}
                if isinstance(payload, str):
                    payload = json.loads(payload)
                if not isinstance(payload, dict) or int(payload.get("id") or 0) != issue_id:
                    entry.update(estado="BLOQUEADO_SNAPSHOT_INVALIDO")
                elif not identificar_vr(payload):
                    entry.update(estado="IGNORADO_NAO_VR")
                elif (payload.get("status") or {}).get("is_closed"):
                    entry.update(estado="IGNORADO_ENCERRADO")
                else:
                    journals = [{"notes": j.get("notas") or "",
                                 "created_on": j.get("criado_em")}
                                for j in snapshot.get("journals", [])]
                    clients = clientes_do_redmine(payload)
                    if len(clients) != 1:
                        entry.update(estado="BLOQUEADO_CLIENTE_AMBIGUO",
                                     clientes_identificados=clients)
                        result.append(entry)
                        continue
                    entry["cliente"] = clients[0]
                    intent = criar_intencao(payload, journals)
                    entry.update(estado=intent["situacao"],
                                 etapa=intent.get("etapa"),
                                 acao=intent.get("acao"),
                                 destino=intent.get("destino"),
                                 versao_redmine=payload.get("updated_on"),
                                 responsavel_atual=(payload.get("assigned_to") or {}).get("id"))
        except (TypeError, ValueError, KeyError) as exc:
            entry.update(estado="BLOQUEADO_DADOS_INVALIDOS", erro=type(exc).__name__)
        result.append(entry)
    return {
        "estado": "CARTEIRA_VR01_PLANEJADA",
        "avaliados": len(result),
        "acionaveis": sum(item["estado"] == "PENDENTE" for item in result),
        "bloqueados": sum(item["estado"].startswith("BLOQUEADO") for item in result),
        "chamados": result,
        "execucao_externa": False,
        "envios_realizados": 0,
        "redmine_escritas": 0,
    }
