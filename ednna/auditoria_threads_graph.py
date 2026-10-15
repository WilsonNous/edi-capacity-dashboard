"""Auditoria read-only das threads ausentes em Sent Items; nunca libera follow-up."""
from __future__ import annotations
import os
from datetime import datetime, timezone


def _data(valor: str):
    try:
        dt = datetime.fromisoformat(str(valor or "").replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def avaliar_candidatos(item: dict, mensagens: list[dict]) -> dict:
    """Um assunto correspondente nao prova identidade; apenas gera proposta humana."""
    cid = int(item.get("chamado_id") or 0)
    inicio = _data(item.get("enviado_em"))
    conversa = str(item.get("graph_conversation_id") or "").strip()
    candidatas = []
    for mensagem in mensagens:
        mid = str(mensagem.get("id") or "").strip()
        conv = str(mensagem.get("conversationId") or "").strip()
        data = _data(mensagem.get("sentDateTime"))
        if not mid or not conv or not data or not inicio or data < inicio:
            continue
        if conversa and conv != conversa:
            continue
        candidatas.append({"message_id": mid, "conversation_id": conv, "sentDateTime": data.isoformat()})
    estado = "CANDIDATO_UNICO_REVISAR" if len(candidatas) == 1 else ("MULTIPLAS_CANDIDATAS_REVISAR" if candidatas else "SEM_EVIDENCIA_SUFiCIENTE")
    return {"chamado_id": cid, "estado": estado, "candidatos": len(candidatas),
            "amostra": candidatas[:3], "thread_reconstruida": False, "envio_permitido": False}


def auditar_threads_ausentes(itens: list[dict], *, limite: int = 3) -> dict:
    """Graph Sent Items pode ser parcial; ausencia nao prova que envio nao ocorreu."""
    from ednna.email_sender import listar_emails_enviados_por_chamado
    remetente = str(os.getenv("EDNNA_EMAIL_FROM", "edi@netunna.com.br") or "").strip()
    pendentes = [x for x in itens if x.get("estado_followup") == "SEM_THREAD"][:max(0, min(int(limite), 5))]
    resultados = []
    for item in pendentes:
        try:
            mensagens = listar_emails_enviados_por_chamado(remetente=remetente, chamado_id=int(item["chamado_id"]), top=500)
            resultados.append(avaliar_candidatos(item, mensagens))
        except Exception as exc:
            resultados.append({"chamado_id": int(item["chamado_id"]), "estado": "GRAPH_INDISPONIVEL",
                               "erro_tipo": type(exc).__name__, "thread_reconstruida": False, "envio_permitido": False})
    return {"avaliados": len(resultados), "itens": resultados, "threads_liberadas": 0}
