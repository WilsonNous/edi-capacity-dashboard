"""Independent EDDY VR01 follow-up planning, no EDNNA dependency."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

FOLLOWUP_HOURS = 48
TERMINAL = ("concluído", "concluido", "fechado", "rejeitado", "closed")


def _dt(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def planejar_followup(decisao: dict, journals: list[dict], *, agora=None) -> dict:
    """Plan 48h after the latest *confirmed outgoing* VR query.

    No outgoing evidence => manual review, never assume that a mention of
    consultation proves an actual send. A new incoming reply suspends follow-up.
    """
    now = _dt(agora) or datetime.now(timezone.utc)
    issue_id = decisao.get("chamado_id")
    estado = str(decisao.get("estado", "")).casefold()
    if any(s in estado for s in TERMINAL) or decisao.get("acao") == "NENHUMA":
        return {"chamado_id": issue_id, "situacao": "SEM_FOLLOWUP", "motivo": "terminal_ou_sem_acao"}
    if decisao.get("acao") != "VERIFICAR_RESPOSTA_VR":
        return {"chamado_id": issue_id, "situacao": "NAO_APLICAVEL"}
    eventos = []
    for journal in journals:
        # These flags must come from verified integration evidence, not free text.
        evidence = journal.get("evidencia_envio") or journal.get("evidencia_resposta")
        when = _dt(journal.get("criado_em") or journal.get("created_on"))
        if evidence and when:
            eventos.append((when, bool(journal.get("evidencia_envio")),
                            bool(journal.get("evidencia_resposta"))))
    sends = [time for time, sent, _ in eventos if sent]
    if not sends:
        return {"chamado_id": issue_id, "situacao": "VALIDAR_ENVIO",
                "motivo": "sem_evidencia_confirmada"}
    latest_send = max(sends)
    if any(time > latest_send and replied for time, _, replied in eventos):
        return {"chamado_id": issue_id, "situacao": "RESPOSTA_RECEBIDA"}
    deadline = latest_send + timedelta(hours=FOLLOWUP_HOURS)
    return {"chamado_id": issue_id,
            "situacao": "FOLLOWUP_VENCIDO" if now >= deadline else "AGUARDANDO_PRAZO",
            "ultimo_envio": latest_send.isoformat(), "vencimento": deadline.isoformat(),
            "horas": FOLLOWUP_HOURS, "execucao_externa": False}
