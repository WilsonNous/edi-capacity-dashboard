"""VR01 pilot follow-up planning and safe scheduler bridge.

Never send automatically: a due follow-up becomes an auditable proposal.
Only explicit action-specific approval can authorize a Graph send later.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ednna.mysql_storage import connect

ISSUE_ID = 50318


def _utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def planejar_followup_piloto(*, agora=None) -> dict:
    """48h since the last confirmed Graph send; any reply requires review."""
    from ednna.eddy_vr01_integrated import _load, _read_issue, _assignee, _identity
    row = _load()
    if not row or row["fase"] != "AGUARDA_CONFIRMACAO_CLIENTE":
        return {"situacao": "FORA_DA_ETAPA", "execucao_externa": False}
    if row["autorizacao_confirmada"]:
        return {"situacao": "AUTORIZACAO_CONFIRMADA", "execucao_externa": False}
    issue = _read_issue(ISSUE_ID)
    if _assignee(issue) != _identity():
        return {"situacao": "BLOQUEADO_ATRIBUICAO", "execucao_externa": False}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) FROM eddy_external_evidence
                WHERE chamado_id=%s AND source='GRAPH' AND evidence_type='INBOX_REPLY'""",
                (ISSUE_ID,))
            replies = int(cur.fetchone()[0])
            if replies:
                return {"situacao": "AGUARDA_REVISAO_RESPOSTA",
                        "respostas": replies, "execucao_externa": False}
            cur.execute("""SELECT MAX(ocorrido_em) FROM eddy_vr01_lifecycle_events
                WHERE chamado_id=%s AND evento IN ('SOLICITACAO_CLIENTE','FOLLOWUP_CLIENTE')""",
                (ISSUE_ID,))
            sent_at = cur.fetchone()[0]
    if not sent_at:
        return {"situacao": "AGUARDA_EVIDENCIA_ENVIO", "execucao_externa": False}
    deadline = _utc(sent_at) + timedelta(hours=48)
    now = _utc(agora) if agora is not None else datetime.now(timezone.utc)
    return {"situacao": "FOLLOWUP_VENCIDO" if now >= deadline else "AGUARDANDO_PRAZO",
            "vencimento": deadline.isoformat(), "execucao_externa": False}


def ciclo_piloto(*, approvals=None, execute=False, agora=None) -> dict:
    """One step per invocation; no automatic email without specific approval."""
    from ednna.eddy_vr01_integrated import planejar_vr01
    plan = planejar_vr01(approvals=approvals, execute=execute)
    if plan.get("acao") != "ACOMPANHAR_E_COBRAR":
        return plan
    followup = planejar_followup_piloto(agora=agora)
    if not execute or followup["situacao"] != "FOLLOWUP_VENCIDO":
        return {**plan, "followup": followup, "envios_realizados": 0}
    from ednna.eddy_vr01_integrated import (
        _approval, _reserve, _advance, _event, _load, _read_issue,
    )
    from ednna.eddy_vr_readiness import verificar_prontidao_vr01
    from ednna.email_sender import enviar_email_graph, localizar_email_enviado
    import os
    issue = _read_issue(ISSUE_ID)
    if not verificar_prontidao_vr01()["pronto"]:
        return {**plan, "followup": followup, "estado": "BLOQUEADO_PRONTIDAO"}
    approved = (approvals or {}).get("FOLLOWUP_CLIENTE")
    _approval("FOLLOWUP_CLIENTE", approvals or {}, issue)
    row = _load()
    if not row or not row["destinatario"] or not row["bp_source_id"]:
        raise RuntimeError("Contato BP de origem nao comprovada")
    subject = str(approved.get("subject") or "")
    if not subject.startswith(f"[EDDY VR01] #{ISSUE_ID} - Follow-up ") or len(subject) > 180:
        raise PermissionError("Assunto unico do follow-up nao aprovado")
    if approved.get("to", "").lower() != row["destinatario"].lower():
        raise PermissionError("Destinatario divergente do BP validado")
    if not _reserve("AGUARDA_CONFIRMACAO_CLIENTE", "FOLLOWUP_CLIENTE"):
        return {**plan, "estado": "AGUARDA_RECONCILIACAO"}
    # Reservation is deliberately retained on any uncertain send result.
    sender = os.environ["EDNNA_EMAIL_FROM"]
    if localizar_email_enviado(remetente=sender, assunto=subject):
        raise RuntimeError("Follow-up anterior detectado: reconciliar")
    enviar_email_graph(remetente=sender, para=[row["destinatario"]], cc=[],
        assunto=subject,
        corpo=("Retomamos a solicitacao de autorizacao no portal VR Beneficios "
               "para o estabelecimento 71676316003323. Por favor, confirme "
               "quando a autorizacao de envio dos arquivos a Netunna for concluida."),
        chamado_id=ISSUE_ID)
    sent = localizar_email_enviado(remetente=sender, assunto=subject)
    if not sent.get("sentDateTime") or not (sent.get("id") or sent.get("internetMessageId")):
        raise RuntimeError("Follow-up pendente de conciliacao Graph")
    _event("FOLLOWUP_CLIENTE", str(sent.get("internetMessageId") or sent["id"]))
    _advance("AGUARDA_CONFIRMACAO_CLIENTE", "FOLLOWUP_CLIENTE",
             "AGUARDA_CONFIRMACAO_CLIENTE")
    return {**plan, "followup": followup, "estado": "FOLLOWUP_CONFIRMADO",
            "envios_realizados": 1}
