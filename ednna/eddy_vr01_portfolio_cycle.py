"""VR Beneficios portfolio lifecycle bridge, reusing the existing VR01 executor."""
from __future__ import annotations

import json
import re
from ednna.eddy_vr01_offline_proposals import listar_chamados_vr_mysql
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.eddy_vr_mysql_sync import clientes_do_redmine
from ednna.eddy_vr_origin import identificar_vr


def _cnpj(issue: dict) -> str | None:
    """Accept only an explicit single CNPJ from the Redmine issue."""
    candidates = set()
    for field in issue.get("custom_fields") or []:
        if "cnpj" not in str(field.get("name") or "").casefold():
            continue
        value = field.get("value")
        for item in (value if isinstance(value, list) else [value]):
            digits = re.sub(r"\D", "", str(item or ""))
            if len(digits) == 14:
                candidates.add(digits)
    return next(iter(candidates)) if len(candidates) == 1 else None


def executar_carteira_vr01(*, ids=None, execute=False, approvals_by_issue=None) -> dict:
    from ednna.eddy_vr01_integrated import (
        _load, _identity, _read_issue, escopo_vr01, planejar_vr01,
    )
    from ednna.eddy_vr_inbox_reconciliation import reconciliar_respostas_vr01
    from ednna.eddy_global_config import enabled

    selected = tuple(dict.fromkeys(int(i) for i in (
        listar_chamados_vr_mysql() if ids is None else ids
    )))
    outcomes = []
    for issue_id in selected:
        entry = {"chamado_id": issue_id, "execucao_externa": False}
        try:
            snapshot = carregar_snapshot(issue_id)
            if not snapshot:
                entry["estado"] = "SEM_SNAPSHOT"
                outcomes.append(entry)
                continue
            issue = snapshot["chamado"].get("payload_json") or {}
            if isinstance(issue, str):
                issue = json.loads(issue)
            if (not isinstance(issue, dict) or int(issue.get("id") or 0) != issue_id
                    or not identificar_vr(issue) or (issue.get("status") or {}).get("is_closed")):
                entry["estado"] = "NAO_ELEGIVEL"
                outcomes.append(entry)
                continue
            if issue.get("_eddy_journals_completos") is not True:
                entry["estado"] = "HISTORICO_INCOMPLETO"
                outcomes.append(entry)
                continue
            clients = clientes_do_redmine(issue)
            cnpj = _cnpj(issue)
            if len(clients) != 1 or not cnpj:
                entry["estado"] = "IDENTIFICACAO_CLIENTE_PENDENTE"
                outcomes.append(entry)
                continue
            # The existing pilot ledger is authoritative about original ownership.
            # New issues use the current Redmine owner only when not already EDDY.
            with escopo_vr01(issue_id, 1, clients[0], cnpj):
                ledger = _load()
            original_owner = (int(ledger["original_owner_id"]) if ledger else
                              int((issue.get("assigned_to") or {}).get("id") or 0))
            if not original_owner or original_owner == _identity():
                entry["estado"] = "RESPONSAVEL_ORIGINAL_NAO_IDENTIFICADO"
                outcomes.append(entry)
                continue
            with escopo_vr01(issue_id, original_owner, clients[0], cnpj):
                if not execute:
                    entry.update(planejar_vr01(execute=False))
                else:
                    # Never initiate a Redmine/Graph action from a stale snapshot.
                    live = _read_issue(issue_id)
                    if live.get("updated_on") != issue.get("updated_on"):
                        entry["estado"] = "SNAPSHOT_DESATUALIZADO"
                    elif len(clientes_do_redmine(live)) != 1 or clientes_do_redmine(live)[0] != clients[0] or _cnpj(live) != cnpj:
                        entry["estado"] = "DADOS_CLIENTE_DIVERGENTES"
                    else:
                        # Run the same audited executor for every eligible issue.
                        # Approval payloads are scoped to the issue; never reuse
                        # one customer's authorization for another ticket.
                        approvals = (approvals_by_issue or {}).get(issue_id, {})
                        try:
                            result = planejar_vr01(execute=True, approvals=approvals)
                            entry.update(result)
                            entry["execucao_externa"] = bool(result.get("externo"))
                        except PermissionError:
                            entry["estado"] = "AGUARDA_APROVACAO_ACAO"
                        # Reply reconciliation is independent of dispatch.
                        ledger = _load()
                        if (ledger and ledger["fase"] == "AGUARDA_CONFIRMACAO_CLIENTE"
                                and not ledger["autorizacao_confirmada"]
                                and enabled("EDDY_VR01_REPLY_RECONCILIATION_READY")):
                            entry["inbox"] = reconciliar_respostas_vr01([issue_id])
            entry["cliente"] = clients[0]
        except Exception as exc:
            entry["estado"] = "FALHA_SEGURA"
            entry["erro"] = type(exc).__name__
        outcomes.append(entry)
    return {"estado": "CARTEIRA_VR01_PROCESSADA", "avaliados": len(outcomes),
            "chamados": outcomes, "execucao_externa": any(
                item.get("execucao_externa") for item in outcomes)}
