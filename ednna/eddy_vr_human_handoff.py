"""VR01: conservative human handoff for inclusion validation.

No mail, ticket write, or auto-close. Requires an explicitly confirmed
customer habilitation reply and an assigned human owner before notification.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


def encaminhar_validacao_inclusao(issue: dict, *, resposta_cliente_confirmada: bool,
                                  validacao_tecnica_confirmada: bool,
                                  responsavel_humano: dict | None,
                                  agora: datetime | None = None) -> dict:
    issue_id = int(issue["id"])
    status = issue.get("status") or {}
    state = str(status.get("name") or "").casefold()
    if status.get("is_closed") or any(s in state for s in ("conclu", "fechado", "rejeitado", "cancelado")):
        return {"chamado_id": issue_id, "situacao": "TERMINAL", "notificar": False}
    subject = str(issue.get("subject") or "")
    if "inclus" not in subject.casefold() and "habilita" not in subject.casefold():
        return {"chamado_id": issue_id, "situacao": "NAO_APLICAVEL", "notificar": False}
    if validacao_tecnica_confirmada:
        return {"chamado_id": issue_id, "situacao": "VALIDACAO_CONFIRMADA", "notificar": False}
    if not resposta_cliente_confirmada:
        return {"chamado_id": issue_id, "situacao": "AGUARDAR_CONFIRMACAO_CLIENTE", "notificar": False}
    owner = responsavel_humano or {}
    address = str(owner.get("email") or "").strip()
    if not address or "@" not in address or not owner.get("nome"):
        return {"chamado_id": issue_id, "situacao": "RESPONSAVEL_HUMANO_NAO_RESOLVIDO",
                "notificar": False}
    now = agora or datetime.now(timezone.utc)
    return {
        "chamado_id": issue_id,
        "situacao": "VALIDACAO_HUMANA_PENDENTE",
        "notificar": True,
        "destinatario": address,
        "responsavel": owner["nome"],
        "assunto": f"[EDDY] Validar recepção de arquivos - chamado #{issue_id}",
        "corpo": (
            f"Olá, {owner['nome']}.\\n\\n"
            f"O cliente confirmou a habilitação referente ao chamado #{issue_id}. "
            "Precisamos da validação técnica no ambiente antes de concluir.\\n"
            f"Solicitação: {subject}\\n\\n"
            "Por favor, consulte o estabelecimento no ambiente operacional, "
            "confirme a recepção e o processamento dos arquivos e registre a evidência no Redmine.\\n"
            "Se não houver arquivos, registre a ausência e a próxima ação necessária.\\n"
            "O EDDY não concluirá este chamado automaticamente."
        ),
        "proximo_followup_em": (now + timedelta(hours=48)).isoformat(),
        "execucao_externa": False,
        "conclusao_automatica_permitida": False,
    }
