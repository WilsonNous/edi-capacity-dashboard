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
    "ERRO_ARQUIVO": "Divergência de registros no arquivo de conciliação",
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
        ("ERRO_ARQUIVO", r"(?:arquivo corrompido|erro de arquivo|trailer de lote|total de registros|registros c1|quantidade de registros|arquivo inconsistente)"),
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


def diagnosticar_trailer_c1(*, total_trailer: int, quantidade_c1: int,
                            arquivo_original_disponivel: bool = False) -> dict:
    """Diagnóstico numérico, não reparação de dados financeiros."""
    informado, encontrado = int(total_trailer), int(quantidade_c1)
    if informado < 0 or encontrado < 0:
        raise ValueError("Contagens negativas não são válidas")
    divergencia = informado - encontrado
    return {
        "tipo": "ERRO_ARQUIVO", "total_trailer": informado, "quantidade_c1": encontrado,
        "diferenca": divergencia, "consistente": divergencia == 0,
        "causa": "INDETERMINADA" if divergencia else "CONTAGEM_COMPATIVEL",
        "arquivo_validado": bool(arquivo_original_disponivel),
        "correcao_automatica_permitida": False,
        "acao": ("Solicitar conferência da origem, verificar registros ausentes e pedir reprocessamento/reenvio "
                 "ou confirmação de erro de geração do trailer") if divergencia else
                 "Validar demais campos do layout antes de liberar importação",
    }


def preparar_despacho_49446() -> dict:
    """Despacho específico, com contexto confirmado no Redmine; não envia."""
    d = diagnosticar_trailer_c1(total_trailer=420, quantidade_c1=393)
    descricao = (
        "Arquivo de conciliação EDENRED_SIMREDEDEPOSTOEXPERS_20260917.txt "
        "(cópia anexada ao Redmine #49446): trailer do lote informa 420 registros, "
        "mas a conferência registrada no chamado identificou 393 registros C1 "
        "(diferença de 27). Solicitamos verificar se faltam registros C1 ou se "
        "o trailer foi gerado incorretamente, informar a causa e, se aplicável, "
        "reprocessar e reenviar o arquivo íntegro. Não autorizamos ajuste manual "
        "do trailer nem descarte de registros."
    )
    r = preparar_despacho(49446, cliente="SIM REDE", descricao_demanda=descricao)
    if not r.get("ok"):
        return r
    # Continuidade de uma solicitação já enviada em 05/10; não é primeiro contato.
    r["assunto"] = "RE: [EXPERS - Arquivos - SIM REDE - CN: 49446]"
    r["corpo"] = (
        "Prezados da equipe de Conciliação Eletrônica, bom dia.\\n\\n"
        "Dando continuidade à solicitação encaminhada em 05/10/2026 ao canal "
        "Concilia Ticket (conciliaticket@edenred.com), recebemos em 08/10/2026 "
        "a orientação de direcionar a análise de arquivos de conciliação eletrônica "
        "a esta equipe.\\n\\n"
        "Reiteramos o problema técnico do chamado Netunna #49446 (SIM REDE / EXPERS): "
        "o trailer de lote informa 420 registros, enquanto a conferência do arquivo "
        "identificou 393 registros C1, diferença de 27. Precisamos confirmar se "
        "faltam registros ou se houve erro na geração do trailer.\\n\\n"
        "Solicitamos análise da origem, confirmação de protocolo e, conforme a "
        "causa identificada, reprocessamento ou reenvio de arquivo íntegro. "
        "O arquivo original e as evidências estão registrados no chamado #49446, "
        "vinculado ao centralizador #49304.\\n\\n"
        "Atenciosamente,\\nEquipe EDI Netunna"
    )
    r["historico_continuidade"] = {
        "primeiro_envio_em": "2026-10-05T09:57:00-03:00",
        "destinatario_original": CAIXA_POSTAL,
        "resposta_orientacao_em": "2026-10-08T09:14:00-03:00",
        "tipo": "REDIRECIONAMENTO_APOS_RESPOSTA",
        "primeira_atuacao_realizada": True,
        "reutilizar_thread_se_confirmada": True,
    }
    r["nao_reenviar_primeira_solicitacao"] = True
    r["requer_verificacao_historico_graph"] = True
    r["exige_nova_autorizacao_de_redirecionamento"] = True
    r["corpo"] += (
        "\n\nReferência de validação: arquivo de 20/09/2026 apresentou 129 "
        "registros C1 e trailer com 129, conforme histórico do chamado. "
        "Solicitamos confirmação de recebimento, protocolo, causa raiz e "
        "previsão de correção/reenvio. O arquivo e capturas constam no Redmine #49446; "
        "anexá-los somente após revisão e autorização."
    )
    r["diagnostico"] = d
    r["anexos_requerem_revisao"] = True
    r["referencia_chamado_pai"] = 49304
    return r
