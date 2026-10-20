"""EDDY: verified email evidence and readable Redmine note, shared by all rules.

This module has no network or Redmine write side effects.
Only provider-confirmed events may trigger follow-up planning.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr
import re


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Data/hora da evidência ausente")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Data/hora da evidência sem fuso")
    return parsed.astimezone(timezone.utc)


def normalizar_evidencia_email(evento: dict, chamado_id: int) -> dict:
    """Require verifiable provider metadata; reject ambiguous/unconfirmed events."""
    if not isinstance(evento, dict) or int(evento.get("chamado_id", 0)) != int(chamado_id):
        raise ValueError("Evidência sem correspondência com o chamado")
    tipo = evento.get("tipo")
    if tipo not in ("ENVIO_CONFIRMADO", "RESPOSTA_RECEBIDA"):
        raise ValueError("Tipo de evidência não confirmado")
    message_id = str(evento.get("message_id") or "").strip()
    provider = str(evento.get("provedor") or "").strip()
    address = str(evento.get("endereco") or "").strip()
    if not message_id or not provider or not address or parseaddr(address)[1] != address:
        raise ValueError("Metadados do provedor incompletos")
    when = _utc(evento.get("ocorrido_em"))
    if tipo == "RESPOSTA_RECEBIDA" and not isinstance(evento.get("corpo_texto"), str):
        raise ValueError("Resposta sem corpo textual")
    return {
        "chamado_id": int(chamado_id),
        "message_id": message_id,
        "provedor": provider,
        "endereco": address,
        "criado_em": when.isoformat(),
        "evidencia_envio": tipo == "ENVIO_CONFIRMADO",
        "evidencia_resposta": tipo == "RESPOSTA_RECEBIDA",
        "corpo_texto": evento.get("corpo_texto") if tipo == "RESPOSTA_RECEBIDA" else None,
    }


def journals_com_evidencias(journals: list[dict], eventos: list[dict], chamado_id: int) -> list[dict]:
    """Append verified events for planning; do not infer sends from Redmine notes."""
    result = list(journals)
    seen = set()
    for event in eventos:
        evidence = normalizar_evidencia_email(event, chamado_id)
        key = (evidence["provedor"], evidence["message_id"], evidence["evidencia_envio"])
        if key in seen:
            continue
        seen.add(key)
        result.append(evidence)
    return result


def nota_resposta_redmine(evento: dict, chamado_id: int, *, analise: str,
                         fase: str, proxima_acao: str) -> str:
    """Preserve the complete new response as plain text, distinct from EDDY's analysis."""
    evidence = normalizar_evidencia_email(evento, chamado_id)
    if not evidence["evidencia_resposta"]:
        raise ValueError("Somente respostas recebidas geram nota de resposta")
    body = evidence["corpo_texto"].replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip():
        raise ValueError("Corpo de resposta vazio")
    # Strip unsafe control characters, retaining readable line breaks/tabs.
    body = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", body)
    subject = str(evento.get("assunto") or "(não informado)")
    return (
        f"EDDY | RESPOSTA DE E-MAIL RECEBIDA\n"
        f"Chamado: #{chamado_id}\n"
        f"Data/hora (UTC): {evidence['criado_em']}\n"
        f"De: {evidence['endereco']}\n"
        f"Assunto: {subject}\n"
        f"ID da mensagem: {evidence['message_id']}\n\n"
        f"RESPOSTA RECEBIDA — TEXTO INTEGRAL\n{body}\n\n"
        f"ANÁLISE DO EDDY\n"
        f"Fase: {fase}\n"
        f"Interpretação: {analise}\n"
        f"Próxima ação: {proxima_acao}"
    )
