"""VR01 state-machine decisions from chronological, attributable Redmine evidence.

Pure planner: never sends email, writes Redmine, or closes a ticket.
Missing evidence is not interpreted as authorization to act.
"""
from __future__ import annotations

import re
from typing import Any

TERMINAL = ("concluído", "concluido", "fechado", "rejeitado", "cancelado", "closed")


def _notes(journals: list[dict]) -> list[dict]:
    return sorted(journals, key=lambda j: str(j.get("created_on") or j.get("criado_em") or ""))


def _origin(text: str, email: str) -> str:
    if "vr.com.br" in email.casefold():
        return "ADQUIRENTE"
    if "netunna.com.br" in email.casefold():
        return "NETUNNA"
    return "CLIENTE" if email else "DESCONHECIDO"


def _email_from_note(text: str) -> str:
    match = re.search(r"(?:^|\n)\s*(?:De|From):\s*[^\n<]*<?([\w.+-]+@[\w.-]+)>?", text, re.I)
    return match.group(1).lower() if match else ""


def decidir_continuidade_vr(issue: dict, journals: list[dict]) -> dict:
    """Return one next action and its owner, without inventing confirmations."""
    issue_id = int(issue["id"])
    status = issue.get("status") or {}
    state = str(status.get("name") or "").casefold()
    base = {"chamado_id": issue_id, "execucao_externa": False,
            "conclusao_automatica_permitida": False}
    if status.get("is_closed") or any(t in state for t in TERMINAL):
        return {**base, "etapa": "TERMINAL", "acao": "NENHUMA", "destino": None}

    subject = str(issue.get("subject") or "").casefold()
    tracker = str((issue.get("tracker") or {}).get("name") or "").casefold()
    entries = _notes(journals)
    body = str(issue.get("description") or "")
    combined = "\n".join([body] + [str(j.get("notes") or j.get("notas") or "") for j in entries])
    # Subject is authoritative when it explicitly says inclusion, even if tracker says falta de arquivo.
    is_inclusion = "inclus" in subject or "habilita" in subject
    if not is_inclusion and any(x in subject or x in tracker for x in ("falta de arquivo", "arquivos faltantes", "salto de nsa")):
        # Never discard the older missing NSA just because a newer gap appeared.
        missing = sorted(set(re.findall(r"\bNSA\s*[:#-]?\s*(\d{2,9})\b", combined, re.I)))
        return {**base, "etapa": "ARQUIVOS_FALTANTES",
                "acao": "VALIDAR_E_SOLICITAR_TODOS_NSAS", "destino": "VR",
                "nsas_mencionados_para_conferencia": missing,
                "observacao": "NSA citado não equivale a NSA faltante; exigir evidência de lacuna e resolução individual."}

    if not is_inclusion:
        return {**base, "etapa": "REVISAO_HUMANA", "acao": "CLASSIFICAR_SOLICITACAO", "destino": "HUMANO"}

    customer_confirmed = False
    vr_confirmed = False
    vr_portal_required = False
    customer_movement = False
    for journal in entries:
        note = str(journal.get("notes") or journal.get("notas") or "")
        # Only the latest message header may identify the sender; quoted email chains
        # are not independent confirmations. Unknown origin cannot authorize progress.
        head = note.split("Em ", 1)[0].split("-----Original Message-----", 1)[0]
        origin = _origin(head, _email_from_note(head))
        lower = head.casefold()
        if origin == "CLIENTE":
            if re.search(r"(habilita.{0,55}(realizad|conclu|efetuad)|j[aá] est[aã]o aparecendo)", lower):
                customer_confirmed = True
            if re.search(r"(j[aá] (tem|t[eê]m|houve|realizamos) (venda|movimenta)|vendas? realizadas?|j[aá] est[aã]o movimentando)", lower):
                customer_movement = True
        elif origin == "ADQUIRENTE":
            if "portal" in lower and ("habilita" in lower or "aceite" in lower):
                vr_portal_required = True
            if re.search(r"(entram automaticamente|arquivo\s+vr_netunna|fluxo de arquivos [eé] iniciado|j[aá] est[aã]o credenciados)", lower):
                vr_confirmed = True

    if vr_confirmed and customer_movement:
        return {**base, "etapa": "VALIDACAO_HUMANA_PENDENTE",
                "acao": "COBRAR_VALIDACAO_RECEPCAO", "destino": "RESPONSAVEL_REDMINE"}
    if vr_confirmed:
        return {**base, "etapa": "MOVIMENTACAO_NAO_CONFIRMADA",
                "acao": "CONSULTAR_MOVIMENTACAO_CLIENTE", "destino": "CLIENTE"}
    if vr_portal_required and not customer_confirmed:
        return {**base, "etapa": "HABILITACAO_CLIENTE_PENDENTE",
                "acao": "COBRAR_HABILITACAO_PORTAL", "destino": "CLIENTE"}
    if customer_confirmed:
        return {**base, "etapa": "VALIDACAO_HUMANA_PENDENTE",
                "acao": "COBRAR_VALIDACAO_RECEPCAO", "destino": "RESPONSAVEL_REDMINE"}
    return {**base, "etapa": "HABILITACAO_NAO_CONFIRMADA",
            "acao": "VERIFICAR_HABILITACAO_COM_CLIENTE", "destino": "CLIENTE"}
