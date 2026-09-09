from __future__ import annotations

import os
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

    return {
        "ok": True,
        "status_code": resposta.status_code,
        "remetente": remetente,
        "para": list(para),
        "cc": list(cc),
        "assunto": assunto,
    }
