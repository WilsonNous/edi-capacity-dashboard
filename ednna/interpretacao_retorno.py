"""Leitura conservadora de respostas externas para continuidade operacional.

Nunca interpreta texto citado de mensagens anteriores como uma resposta nova.
A saída é uma proposta de ação, não uma autorização para enviar e-mail.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


def _texto_novo(corpo: str) -> str:
    texto = html.unescape(re.sub(r"<[^>]+>", " ", str(corpo or "")))
    cortes = [
        r"(?im)^\s*(?:em|on)\s+.+(?:escreveu|wrote):",
        r"(?im)^\s*de:\s+.+",
        r"(?im)^\s*from:\s+.+",
        r"(?im)^\s*[-]{2,}\s*(?:original message|mensagem original)",
        r"(?im)^\s*ativado\s+.+escreveu:",
    ]
    for padrao in cortes:
        match = re.search(padrao, texto)
        if match:
            texto = texto[:match.start()]
    return " ".join(texto.split()).strip()


def interpretar_retorno(corpo: str, *, assunto: str = "", recebido_em: str = "") -> dict:
    """Retorna evidência, protocolo, pendência e sugestão de prazo sem executar efeitos."""
    texto = _texto_novo(corpo)
    # Prioriza a regra de redirecionamento explícito Edenred/EXPERS.
    # Não classifica o aviso como habilitação ou resolução.
    from ednna.regra_expers_edenred import interpretar_orientacao_retorno
    orientacao = interpretar_orientacao_retorno(texto, assunto=assunto)
    if orientacao:
        return orientacao
    normalizado = texto.casefold()
    protocolo = re.search(r"protocolo(?:\s+de\s+atendimento)?\s*[:#-]?\s*(\d{4,})", texto, re.I)
    greencard = "greencard" in (assunto + " " + texto).casefold()
    exige_termo = bool(re.search(r"termo.{0,100}(?:preenchid|assinad|formalizad)", normalizado))
    condiciona = any(t in normalizado for t in ("somente serão realizadas", "não serão aceitas", "mediante o envio"))
    pede_identidade = bool(re.search(r"documento.{0,45}(?:foto|identifica)", normalizado))
    preferencial = "preferencialmente" in normalizado
    evidencia = texto[:700]
    if greencard and exige_termo and condiciona:
        return {
            "classificacao": "PENDENCIA_DOCUMENTAL",
            "estado_sugerido": "AGUARDANDO_DOCUMENTACAO",
            "protocolo": protocolo.group(1) if protocolo else "",
            "documentos_obrigatorios": ["termo preenchido e assinado pelo proprietario ou responsavel legal"],
            "documentos_recomendados": ["documento com foto do responsavel"] if pede_identidade and preferencial else [],
            "documentos_adicionais_a_verificar": ["documento com foto do responsavel"] if pede_identidade and not preferencial else [],
            "proxima_acao": "Verificar termo valido nos anexos e solicitar ao cliente/responsavel autorizado se ausente",
            "followup_externo_permitido": False,
            "requer_validacao_humana": True,
            "confianca": "ALTA",
            "evidencia": evidencia,
            "prazo_revisao_em": _prazo_revisao(recebido_em),
            "politica_prazo": "48_HORAS_APOS_RECEBIMENTO; revisar prazo se a pendencia for registrada posteriormente",
        }
    return {
        "classificacao": "REVISAO_HUMANA",
        "estado_sugerido": "AGUARDANDO_INTERPRETACAO",
        "protocolo": protocolo.group(1) if protocolo else "",
        "proxima_acao": "Interpretar resposta integral e decidir continuidade",
        "followup_externo_permitido": False,
        "requer_validacao_humana": True,
        "confianca": "INSUFICIENTE",
        "evidencia": evidencia,
        "prazo_revisao_em": "",
    }


def _prazo_revisao(recebido_em: str) -> str:
    try:
        data = datetime.fromisoformat(str(recebido_em or "").replace("Z", "+00:00"))
        if data.tzinfo is None:
            return ""  # Sem timezone, não inventar instante absoluto.
        return (data.astimezone(TZ) + timedelta(hours=48)).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return ""
