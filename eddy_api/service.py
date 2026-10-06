from __future__ import annotations
from typing import Any
from ui.operational_data import resumo, resumo_trabalho_ednna
from ednna.homologacao import estado_regra
from redmine_api import buscar_detalhes_chamado

CAPABILITIES = (
    "edi.status.get",
    "edi.issue.inspect",
    "edi.player.inspect",
    "edi.rule.list",
)

def status_get(_: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    r = resumo()
    t = resumo_trabalho_ednna()
    output = {
        "active_issues": int(r.get("total") or 0),
        "awaiting_third_parties": int(r.get("terceiros") or 0),
        "human_decisions": int(r.get("revisao") or 0),
        "rules": int(r.get("regras") or 0),
        "homologated_rules": int(r.get("homologadas") or 0),
        "automatic_rules": int(t.get("regras_automaticas") or 0),
        "under_monitoring": int(t.get("acompanhando") or 0),
        "executions": int(t.get("atuacoes") or 0),
        "followups": int(t.get("followups") or 0),
    }
    return output, 0.98, [{"source": "eddy:operational_snapshot"}], [], False

def issue_inspect(data: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    issue_id = data.get("issue_id") or data.get("id")
    if not issue_id:
        raise ValueError("issue_id é obrigatório.")
    issue = buscar_detalhes_chamado(int(issue_id), incluir_journals=False, incluir_relacoes=False,
                                    incluir_anexos=False, consulta_pontual=False, tentativas=1) or {}
    issue = issue.get("issue", issue) if isinstance(issue, dict) else {}
    if not issue:
        raise LookupError("Chamado não encontrado.")
    safe = {k: issue.get(k) for k in ("id","subject","status","priority","project","assigned_to",
                                      "created_on","updated_on","closed_on") if k in issue}
    return safe, 0.97, [{"source": f"redmine:issue:{issue_id}"}], [], False

def player_inspect(data: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    player = str(data.get("player") or "").strip()
    if not player:
        raise ValueError("player é obrigatório.")
    # Primeira versão é deliberadamente conservadora: não fabrica conhecimento agregado.
    return {"player": player, "message": "Consulta agregada de player ainda não materializada no contrato v1."}, 0.40, [], ["Evidência agregada insuficiente; requer análise humana."], True

def rule_list(data: dict[str, Any]) -> tuple[dict, float, list, list, bool]:
    # O domínio possui múltiplas fontes de regras; v1 não deve fingir um catálogo único.
    rid = str(data.get("rule_id") or "").strip()
    if rid:
        state = estado_regra(rid)
        if state:
            return {"rules": [state]}, 0.99, [{"source": f"eddy:homologacao:{rid}"}], [], False
        return {"rules": []}, 0.80, [], ["Regra não encontrada entre as homologações."], True
    return {"rules": []}, 0.50, [], ["Listagem consolidada será ligada ao catálogo canônico em incremento posterior."], True

ROUTES = {
    "edi.status.get": status_get,
    "edi.issue.inspect": issue_inspect,
    "edi.player.inspect": player_inspect,
    "edi.rule.list": rule_list,
}
