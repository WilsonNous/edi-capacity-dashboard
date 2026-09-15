from __future__ import annotations

import os
import re
from typing import Iterable

import requests


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
TOKEN_URL_TEMPLATE = (
    "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
)


class EmailConfigError(RuntimeError):
    pass


class EmailSendError(RuntimeError):
    pass


def _obrigatoria(nome: str) -> str:
    valor = str(os.getenv(nome, "") or "").strip()

    if not valor:
        raise EmailConfigError(
            f"Variável obrigatória ausente: {nome}"
        )

    return valor


def _destinatarios(lista: Iterable[str]) -> list[dict]:
    resultado = []

    for email in lista or []:
        email = str(email or "").strip()

        if email:
            resultado.append(
                {
                    "emailAddress": {
                        "address": email
                    }
                }
            )

    return resultado


def obter_token_graph() -> str:
    tenant_id = _obrigatoria("AZURE_TENANT_ID")
    client_id = _obrigatoria("AZURE_CLIENT_ID")
    client_secret = _obrigatoria("AZURE_CLIENT_SECRET")

    resposta = requests.post(
        TOKEN_URL_TEMPLATE.format(
            tenant_id=tenant_id
        ),
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=20,
    )

    if resposta.status_code != 200:
        raise EmailSendError(
            "Falha ao obter token do Microsoft Graph: "
            f"HTTP {resposta.status_code} - "
            f"{resposta.text[:500]}"
        )

    token = str(
        resposta.json().get("access_token", "")
        or ""
    ).strip()

    if not token:
        raise EmailSendError(
            "Microsoft Graph não retornou access_token."
        )

    return token


def enviar_email_graph(
    *,
    remetente: str,
    para: list[str],
    cc: list[str],
    assunto: str,
    corpo: str,
) -> dict:
    remetente = str(
        remetente
        or os.getenv(
            "EDNNA_EMAIL_FROM",
            "edi@netunna.com.br",
        )
        or ""
    ).strip()

    if not remetente:
        raise EmailConfigError(
            "Remetente não configurado."
        )

    if not para:
        raise EmailConfigError(
            "Nenhum destinatário informado."
        )

    token = obter_token_graph()

    resposta = requests.post(
        f"{GRAPH_BASE_URL}/users/{remetente}/sendMail",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "message": {
                "subject": assunto,
                "body": {
                    "contentType": "Text",
                    "content": corpo,
                },
                "toRecipients": _destinatarios(
                    para
                ),
                "ccRecipients": _destinatarios(
                    cc
                ),
            },
            "saveToSentItems": True,
        },
        timeout=30,
    )

    if resposta.status_code != 202:
        raise EmailSendError(
            "Falha ao enviar e-mail pelo Microsoft Graph: "
            f"HTTP {resposta.status_code} - "
            f"{resposta.text[:800]}"
        )

    resultado = {
        "ok": True,
        "status_code": resposta.status_code,
        "remetente": remetente,
        "para": list(para),
        "cc": list(cc),
        "assunto": assunto,
        "message_id": "",
        "conversation_id": "",
        "internet_message_id": "",
    }

    # A leitura de Itens Enviados é apenas enriquecimento.
    # Se Mail.Read ainda não estiver concedido, o envio continua válido.
    try:
        enviado = localizar_email_enviado(
            remetente=remetente,
            assunto=assunto,
        )
        resultado["message_id"] = str(enviado.get("id", "") or "")
        resultado["conversation_id"] = str(enviado.get("conversationId", "") or "")
        resultado["internet_message_id"] = str(enviado.get("internetMessageId", "") or "")
    except Exception as exc:
        resultado["metadata_warning"] = str(exc)[:500]

    return resultado


def _graph_get(
    url: str,
    *,
    params: dict | None = None,
    timeout: int = 30,
) -> dict:
    token = obter_token_graph()
    resposta = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        params=params or {},
        timeout=timeout,
    )

    if resposta.status_code != 200:
        raise EmailSendError(
            "Falha ao consultar Microsoft Graph: "
            f"HTTP {resposta.status_code} - {resposta.text[:800]}"
        )

    return resposta.json()


def localizar_email_enviado(
    *,
    remetente: str,
    assunto: str,
) -> dict:
    """Localiza a cópia mais recente do e-mail em Itens Enviados."""
    dados = _graph_get(
        f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",
        params={
            "$select": "id,subject,conversationId,internetMessageId,sentDateTime",
            "$orderby": "sentDateTime desc",
            "$top": "25",
        },
    )

    alvo = str(assunto or "").strip().casefold()
    for item in dados.get("value", []):
        if str(item.get("subject", "") or "").strip().casefold() == alvo:
            return item
    return {}


def listar_mensagens_conversa(
    *,
    caixa_postal: str,
    conversation_id: str,
    recebidas_apos: str = "",
) -> list[dict]:
    """Busca mensagens da conversa sem $filter complexo no Graph.

    Exchange pode responder InefficientFilter ao combinar conversationId, data e
    orderby. Buscamos uma janela recente da Inbox e filtramos localmente.
    """
    dados = _graph_get(
        f"{GRAPH_BASE_URL}/users/{caixa_postal}/mailFolders/inbox/messages",
        params={
            "$select": (
                "id,subject,conversationId,internetMessageId,receivedDateTime,"
                "from,body,bodyPreview,isRead"
            ),
            "$orderby": "receivedDateTime desc",
            "$top": "100",
        },
    )
    itens = []
    alvo = str(conversation_id or "")
    for item in dados.get("value", []) or []:
        if str(item.get("conversationId", "") or "") != alvo:
            continue
        if recebidas_apos and str(item.get("receivedDateTime", "") or "") < str(recebidas_apos):
            continue
        itens.append(item)
    itens.sort(key=lambda x: str(x.get("receivedDateTime", "") or ""))
    return itens



def localizar_email_enviado_por_chamado(*, remetente: str, chamado_id: int) -> dict:
    """Reconciliação: localiza na pasta Enviados a mensagem mais recente contendo #ID no assunto."""
    dados = _graph_get(
        f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",
        params={
            "$select": "id,subject,conversationId,internetMessageId,sentDateTime,from,toRecipients,ccRecipients",
            "$orderby": "sentDateTime desc",
            "$top": "250",
        },
    )
    alvo = f"#{int(chamado_id)}"
    for item in dados.get("value", []) or []:
        if alvo in str(item.get("subject", "") or ""):
            return item
    return {}

def localizar_resposta_por_chamado(*, caixa_postal: str, chamado_id: int, recebidas_apos: str = "") -> dict:
    """Fallback robusto: localiza resposta na Inbox pelo #ID, tolerando RE:/[EXT]."""
    dados = _graph_get(
        f"{GRAPH_BASE_URL}/users/{caixa_postal}/mailFolders/inbox/messages",
        params={
            "$select": "id,subject,conversationId,internetMessageId,receivedDateTime,from,body,bodyPreview,isRead",
            "$orderby": "receivedDateTime desc",
            "$top": "500",
        },
    )
    alvo = f"#{int(chamado_id)}"
    for item in dados.get("value", []) or []:
        assunto = str(item.get("subject", "") or "")
        if alvo not in assunto:
            continue
        if recebidas_apos and str(item.get("receivedDateTime", "") or "") < str(recebidas_apos):
            continue
        return item
    return {}


def listar_envios_cancelamento_getnet(*, remetente: str, top: int = 250) -> list[dict]:
    """Descobre atuações GETNET diretamente em Sent Items, sem depender do snapshot Redmine."""
    dados = _graph_get(
        f"{GRAPH_BASE_URL}/users/{remetente}/mailFolders/sentitems/messages",
        params={
            "$select": "id,subject,conversationId,internetMessageId,sentDateTime,from,toRecipients,ccRecipients",
            "$orderby": "sentDateTime desc",
            "$top": str(max(25, min(int(top or 250), 500))),
        },
    )
    resultado = []
    for item in dados.get("value", []) or []:
        assunto = str(item.get("subject", "") or "")
        baixo = assunto.casefold()
        if "getnet" not in baixo or "cancel" not in baixo:
            continue
        m = re.search(r"#\s*(\d{3,})\b", assunto)
        if not m:
            continue
        copia = dict(item)
        copia["chamado_id"] = int(m.group(1))
        resultado.append(copia)
    return resultado
