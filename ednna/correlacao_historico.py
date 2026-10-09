"""Correlação auditável de histórico Redmine e evidências de e-mail.

Nunca considera um texto colado no journal como confirmação de envio Graph.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
SENHA = re.compile(r"(?im)^(\s*(?:senha|password|token|api[_ -]?key|secret)\s*:\s*).+$")
CHAMADO = re.compile(r"(?<!\d)#?(\d{4,7})(?!\d)")
CABECALHO = re.compile(r"(?im)^\s*(?:De|From|Para|To|Cc|Assunto|Subject|Enviad[ao]s?|Sent)\s*:")
ENVIADO = re.compile(r"(?im)^\s*(?:Enviad[ao]s?|Sent)\s*:")
TERCEIRO = re.compile(r"aguardando retorno (?:adquirente|terceiro)|espera de terceiro", re.I)


def mascarar_segredos(texto: str) -> str:
    return SENHA.sub(r"\1[REDACTED]", str(texto or ""))


def _texto_journal(journal: dict) -> str:
    return str(journal.get("notes") or "")


def correlacionar_historico(issue: dict, mensagens: list[dict] | None = None,
                           *, caixas_consultadas: list[str] | None = None) -> dict[str, Any]:
    """Reconstrói evidências sem inferir envio de mensagem a partir do journal.

    mensagens: itens previamente consultados no Microsoft Graph, contendo id,
    internetMessageId, subject, sentDateTime/receivedDateTime e from/toRecipients.
    """
    numero = int(issue.get("id") or 0)
    journals = issue.get("journals") or []
    eventos = []
    for j in journals:
        texto = _texto_journal(j)
        if not texto.strip():
            continue
        contem_email = bool(CABECALHO.search(texto) and EMAIL.search(texto))
        eventos.append({
            "fonte": "REDMINE_JOURNAL",
            "id": str(j.get("id") or ""),
            "data": j.get("created_on"),
            "tipo": "EMAIL_TRANSCRITO" if contem_email else "NOTA",
            "evidencia_envio_confirmado": False,
            "assunto_relacionado": str(numero) in texto,
            "remetentes_detectados": sorted(set(EMAIL.findall(texto)))[:12],
            "resumo": mascarar_segredos(texto)[:300],
        })

    confirmadas = []
    for msg in mensagens or []:
        assunto = str(msg.get("subject") or "")
        texto_ref = " ".join([assunto, str(msg.get("conversationId") or "")])
        # Não associar mensagens por mera coincidência de remetente.
        ids = {int(n) for n in CHAMADO.findall(texto_ref)}
        if numero not in ids:
            continue
        ident = msg.get("internetMessageId") or msg.get("id")
        if not ident:
            continue
        confirmadas.append({
            "fonte": "MICROSOFT_GRAPH",
            "id": str(ident),
            "data": msg.get("sentDateTime") or msg.get("receivedDateTime"),
            "tipo": "MENSAGEM_VERIFICADA",
            "evidencia_envio_confirmado": bool(msg.get("sentDateTime")),
            "assunto_relacionado": True,
        })
    eventos.extend(confirmadas)
    eventos.sort(key=lambda e: str(e.get("data") or ""))
    status = str((issue.get("status") or {}).get("name") or "")
    ultimo = eventos[-1] if eventos else None
    return {
        "chamado_id": numero,
        "status_redmine": status,
        "eventos": eventos,
        "total_journals_com_email": sum(e["tipo"] == "EMAIL_TRANSCRITO" for e in eventos),
        "mensagens_graph_verificadas": len(confirmadas),
        "envio_confirmado_graph": any(e["evidencia_envio_confirmado"] for e in confirmadas),
        "caixas_consultadas": caixas_consultadas or [],
        "consulta_email_realizada": caixas_consultadas is not None,
        "estado": ("EVIDENCIA_GRAPH_CORRELACIONADA" if confirmadas else
                   "HISTORICO_DOCUMENTAL_SEM_CONFIRMACAO_GRAPH" if eventos else
                   "SEM_EVIDENCIA"),
        "proxima_acao": ("Acompanhar retorno e validar pendências no histórico" if
                         TERCEIRO.search(status) or "AGUARDANDO RETORNO" in status.upper()
                         else "Revisar a sequência cronológica e definir próxima ação"),
        "ultima_evidencia": ultimo,
        "transferencia_automatica": False,
        "envio_externo_autorizado": False,
    }


def analisar_chamado(chamado_id: int) -> dict:
    """Consulta pontual ao Redmine com journals; não consulta caixas implicitamente."""
    from redmine_api import buscar_detalhes_chamado
    issue = buscar_detalhes_chamado(int(chamado_id), incluir_journals=True)
    return correlacionar_historico(issue)
