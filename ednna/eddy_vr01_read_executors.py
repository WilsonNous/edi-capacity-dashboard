"""VR01 read-side executors. No Redmine PUT, Graph send or state advancement.

A positive client authorization is never inferred from a message. The monitor
returns evidence candidates for human/authorized verification.
"""
from __future__ import annotations

import os
import time
from typing import Callable

ISSUE_ID = 50318


def read_redmine_journals(*, issue_id: int = ISSUE_ID, attempts: int = 3,
                          fetch: Callable | None = None,
                          sleep: Callable = time.sleep) -> dict:
    """Retry GET only; never retry a Redmine mutation after a timeout."""
    if issue_id != ISSUE_ID:
        raise ValueError("VR01 pilot issue mismatch")
    if not 1 <= attempts <= 5:
        raise ValueError("attempts must be 1..5")
    if fetch is None:
        import requests
        from redmine_api import REDMINE_URL, _headers

        def fetch():
            response = requests.get(
                f"{REDMINE_URL}/issues/{issue_id}.json",
                headers=_headers(), params={"include": "journals"},
                timeout=(8, 20),
            )
            response.raise_for_status()
            return response.json()
    for attempt in range(attempts):
        try:
            data = fetch()
            issue = data.get("issue") if isinstance(data, dict) else None
            if not isinstance(issue, dict) or int(issue.get("id", 0)) != issue_id:
                return {"estado": "RESPOSTA_INVALIDA", "journals": [], "confirmado": False}
            journals = issue.get("journals")
            if not isinstance(journals, list):
                return {"estado": "JOURNALS_AUSENTES", "journals": [], "confirmado": False}
            journals = sorted(journals, key=lambda j: (str(j.get("created_on") or ""), int(j.get("id") or 0)))
            return {"estado": "LEITURA_CONFIRMADA", "journals": journals,
                    "responsavel_id": int((issue.get("assigned_to") or {}).get("id") or 0),
                    "updated_on": issue.get("updated_on"), "confirmado": True}
        except Exception as exc:
            # Never include credentials, URLs with tokens or response bodies.
            if attempt == attempts - 1:
                return {"estado": "REDMINE_INDISPONIVEL", "erro": type(exc).__name__,
                        "journals": [], "confirmado": False}
            sleep(min(2 ** attempt, 4))
    raise AssertionError("unreachable")


def monitor_graph_replies(*, caixa_postal: str | None = None,
                          conversation_id: str, sent_at: str,
                          list_messages: Callable | None = None) -> dict:
    """Collect correlated replies; none constitutes verified portal authorization."""
    if not conversation_id or not sent_at:
        return {"estado": "SEM_REFERENCIA_ENVIO", "respostas": [], "autorizacao_confirmada": False}
    if list_messages is None:
        from ednna.email_sender import listar_mensagens_conversa
        list_messages = listar_mensagens_conversa
    mailbox = caixa_postal or os.getenv("EDNNA_EMAIL_FROM", "")
    if not mailbox:
        return {"estado": "CAIXA_POSTAL_AUSENTE", "respostas": [], "autorizacao_confirmada": False}
    try:
        messages = list_messages(caixa_postal=mailbox, conversation_id=conversation_id,
                                 recebidas_apos=sent_at)
    except Exception as exc:
        return {"estado": "GRAPH_INDISPONIVEL", "erro": type(exc).__name__,
                "respostas": [], "autorizacao_confirmada": False}
    candidates = []
    seen = set()
    for item in messages:
        if item.get("conversationId") != conversation_id:
            continue
        when = str(item.get("receivedDateTime") or "")
        if not when or when < sent_at:
            continue
        key = str(item.get("internetMessageId") or item.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append({"message_id": key, "received_at": when,
                           "from": str(((item.get("from") or {}).get("emailAddress") or {}).get("address") or "")})
    return {"estado": "RESPOSTAS_LOCALIZADAS" if candidates else "AGUARDANDO_RESPOSTA",
            "respostas": candidates, "autorizacao_confirmada": False}


def verificar_validacao_adquirente(*, portal_evidence_id: str = "",
                                  arquivo_evidence_id: str = "",
                                  verificador: Callable | None = None) -> dict:
    """Only independent verified evidence may mark file receipt as validated."""
    if not portal_evidence_id or not arquivo_evidence_id or verificador is None:
        return {"estado": "VALIDACAO_PENDENTE", "validado": False}
    try:
        portal = verificador("AUTORIZACAO_PORTAL", portal_evidence_id)
        arquivo = verificador("ARQUIVO_RECEBIDO", arquivo_evidence_id)
    except Exception as exc:
        return {"estado": "VALIDACAO_INDISPONIVEL", "erro": type(exc).__name__, "validado": False}
    if portal is not True or arquivo is not True:
        return {"estado": "EVIDENCIA_NAO_CONFIRMADA", "validado": False}
    return {"estado": "VALIDACAO_CONFIRMADA", "validado": True,
            "portal_evidence_id": portal_evidence_id, "arquivo_evidence_id": arquivo_evidence_id}
