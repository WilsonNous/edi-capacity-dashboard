"""Regra EXPERS / Edenred — roteamento oficial informado em 08/10/2026.

Fonte: resposta de conciliaticket@edenred.com ao chamado #49446.
A regra classifica e prepara rascunho; não envia mensagens nem altera Redmine.
"""
from __future__ import annotations

import re
import unicodedata

REGRA_ID = "EXPERS-EDENRED-CANAL-001"
CAIXA_POSTAL = "conciliaticket@edenred.com"
CONCILIACAO = "conciliacaoeletronica-br@edenred.com"
ASSUNTOS_CONCILIACAO = {
    "AUSENCIA_ARQUIVO": "Ausência de arquivo",
    "INCLUSAO_CONTRATO": "Inclusão de contrato na caixa postal",
    "ALERTAS": "Alertas",
    "AUSENCIA_VENDAS": "Ausência de vendas no arquivo",
    "CANCELAMENTO_CAIXA": "Cancelamento de caixa postal",
}
FONTE = "E-mail de Marcos Sudré, EBR - Concilia Ticket, 08/10/2026 09:14, chamado #49446"


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "").casefold())
    return "".join(c for c in t if not unicodedata.combining(c))


def classificar_demanda(texto: str) -> dict:
    """Falha fechada em caso de ambiguidade, sobretudo abrir x cancelar caixa."""
    t = _norm(texto)
    regras = (
        ("CANCELAMENTO_CAIXA", r"cancel(?:amento|ar|acao).{0,45}caixa postal"),
        ("INCLUSAO_CONTRATO", r"(?:inclusao|incluir|adicionar).{0,45}contrato.{0,60}caixa postal"),
        ("AUSENCIA_VENDAS", r"(?:ausencia|falta|sem|nao ha).{0,35}vendas?.{0,45}arquivo"),
        ("AUSENCIA_ARQUIVO", r"(?:ausencia|falta|sem|nao receb|nao chegou).{0,45}arquiv"),
        ("ALERTAS", r"\balertas?\b"),
        ("ABERTURA_CAIXA", r"(?:abertura|abrir|criar|habilitar).{0,35}caixa postal"),
    )
    encontrados = [tipo for tipo, padrao in regras if re.search(padrao, t)]
    if len(encontrados) != 1:
        return {"tipo": "REVISAO_HUMANA", "destinatario": "", "confianca": "INSUFICIENTE",
                "motivo": "Demanda não identificada de forma única" if not encontrados else "Tipos de demanda conflitantes"}
    tipo = encontrados[0]
    return {"tipo": tipo, "destinatario": CAIXA_POSTAL if tipo == "ABERTURA_CAIXA" else CONCILIACAO,
            "confianca": "ALTA", "motivo": FONTE}


def interpretar_orientacao_retorno(corpo: str, *, assunto: str = "") -> dict | None:
    """Identifica somente a orientação de canais, sem tratá-la como solução."""
    t = _norm(corpo)
    if not ("concilia ticket" in t and "abertura de caixa postal" in t
            and CONCILIACAO in t and "ausencia de arquivo" in t):
        return None
    if "expers" not in _norm(assunto + " " + corpo) and "edenred" not in t:
        return None
    return {
        "classificacao": "REDIRECIONAMENTO_CANAL",
        "estado_sugerido": "AGUARDANDO_REENCAMINHAMENTO",
        "protocolo": "",
        "regra_id": REGRA_ID,
        "canal_caixa_postal": CAIXA_POSTAL,
        "canal_conciliacao": CONCILIACAO,
        "proxima_acao": "Identificar o tipo exato de solicitação do #49446, validar destinatário e preparar reencaminhamento para a equipe correta",
        "followup_externo_permitido": False,
        "requer_validacao_humana": True,
        "confianca": "ALTA",
        "evidencia": str(corpo or "")[:700],
        "prazo_revisao_em": "",
        "fonte": FONTE,
    }


def preparar_despacho(chamado_id: int, *, cliente: str, descricao_demanda: str,
                       identificadores: list[str] | None = None) -> dict:
    """Prepara despacho para aprovação; nunca presume contrato/arquivo ausente."""
    classificacao = classificar_demanda(descricao_demanda)
    if classificacao["tipo"] == "REVISAO_HUMANA":
        return {"ok": False, "estado": "REVISAO_HUMANA", "motivo": classificacao["motivo"],
                "regra_id": REGRA_ID}
    ids = [str(x).strip() for x in (identificadores or []) if str(x).strip()]
    assunto = f"[EXPERS - {ASSUNTOS_CONCILIACAO.get(classificacao['tipo'], 'Abertura de caixa postal')} - {cliente} - CN: {int(chamado_id)}]"
    corpo = [
        "Prezados, bom dia.",
        "",
        "Conforme orientação recebida da equipe Concilia Ticket em 08/10/2026,",
        "encaminhamos ao canal responsável a solicitação abaixo:",
        f"Cliente: {cliente}",
        f"Chamado Netunna: #{int(chamado_id)}",
        f"Tipo: {ASSUNTOS_CONCILIACAO.get(classificacao['tipo'], 'Abertura de caixa postal')}",
        f"Descrição informada: {descricao_demanda.strip()}",
    ]
    if ids:
        corpo.append("Identificadores informados: " + "; ".join(ids))
    corpo += ["", "Solicitamos análise e orientação sobre a continuidade deste atendimento.",
              "Favor informar protocolo e eventual documentação necessária.", "",
              "Atenciosamente,", "Equipe EDI Netunna"]
    return {
        "ok": True, "regra_id": REGRA_ID, "chamado_id": int(chamado_id),
        "tipo": classificacao["tipo"], "para": [classificacao["destinatario"]],
        "cc": [], "assunto": assunto, "corpo": "\n".join(corpo),
        "estado": "AGUARDANDO_APROVACAO_ENVIO",
        "requer_validacao_humana": True, "envio_executado": False,
        "preflight_obrigatorio": True, "verificar_duplicidade": True,
        "fonte": FONTE,
    }
