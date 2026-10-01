"""Compatibilidade v3.34.13+ para descoberta de retornos na Inbox."""
from __future__ import annotations


def instalar() -> None:
    from ednna import email_sender as sender

    def listar_mensagens_conversa(*, caixa_postal: str, conversation_id: str, recebidas_apos: str = "") -> list[dict]:
        dados = sender._graph_get(
            f"{sender.GRAPH_BASE_URL}/users/{caixa_postal}/mailFolders/inbox/messages",
            params={"$select": "id,subject,conversationId,internetMessageId,receivedDateTime,from,body,bodyPreview,isRead", "$orderby": "receivedDateTime desc", "$top": "500"},
        )
        itens=[]; alvo=str(conversation_id or "")
        for item in dados.get("value", []) or []:
            if str(item.get("conversationId", "") or "") != alvo: continue
            if recebidas_apos and str(item.get("receivedDateTime", "") or "") < str(recebidas_apos): continue
            itens.append(item)
        itens.sort(key=lambda x: str(x.get("receivedDateTime", "") or "")); return itens

    def localizar_resposta_por_chamado(*, caixa_postal: str, chamado_id: int, recebidas_apos: str = "") -> dict:
        dados = sender._graph_get(
            f"{sender.GRAPH_BASE_URL}/users/{caixa_postal}/mailFolders/inbox/messages",
            params={"$select": "id,subject,conversationId,internetMessageId,receivedDateTime,from,body,bodyPreview,isRead", "$orderby": "receivedDateTime desc", "$top": "500"},
        )
        for item in dados.get("value", []) or []:
            assunto=str(item.get("subject", "") or "")
            if not sender._assunto_referencia_chamado(assunto, int(chamado_id)): continue
            if recebidas_apos and str(item.get("receivedDateTime", "") or "") < str(recebidas_apos): continue
            print(f"[EDNNA] Monitor e-mail | resposta correlacionada | chamado={int(chamado_id)} | assunto={assunto[:160]}", flush=True); return item
        print(f"[EDNNA] Monitor e-mail | sem resposta correlacionada | chamado={int(chamado_id)} | formatos=#ID,CN:ID,[ID] | janela=500", flush=True); return {}

    sender.listar_mensagens_conversa=listar_mensagens_conversa
    sender.localizar_resposta_por_chamado=localizar_resposta_por_chamado

    # v3.34.14: o instalador já executado pelo pacote também conecta os checkpoints
    # humanos pendentes ao ciclo de monitoramento, sem concluí-los automaticamente.
    try:
        from ednna.checkpoint_email_monitor_v3414 import instalar as instalar_checkpoints
        instalar_checkpoints()
    except Exception as exc:
        print(f"[EDNNA] Monitor checkpoint | instalação adiada | {type(exc).__name__}: {exc}", flush=True)
