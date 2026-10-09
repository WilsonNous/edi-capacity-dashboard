"""Motor de abertura de relacionamento do EDDY.

Primeira fase: planejamento seguro e auditável. Nenhuma ação externa é
executada por este módulo; o executor precisa ser homologado separadamente.
"""
from __future__ import annotations

from ednna.aprendizado_operacional import obter_autorizacao_motor
from ednna.homologacao import estado_regra, listar_homologacoes_mais_recentes
from ednna.minerador_aberturas import listar_propostas
from ednna.armazenamento import conectar, agora_brasil_iso


def avaliar_abertura(regra_id: str, *, dados: dict | None = None) -> dict:
    """Resolve homologação, autorização e checkpoints sem confundir inclusão."""
    rid = str(regra_id or "").strip()
    dados = dict(dados or {})
    if not rid.startswith("ABERTURA-"):
        return {"regra_id": rid, "estado": "OPERACAO_INCOMPATIVEL", "executavel": False}
    homologacao = estado_regra(rid) or {}
    if homologacao.get("estado") not in {"ATIVA", "EM_OBSERVACAO"}:
        return {"regra_id": rid, "estado": "NAO_HOMOLOGADA_OU_SUSPENSA", "executavel": False}
    autorizacao = obter_autorizacao_motor(rid) or {}
    modo = str(autorizacao.get("modo") or "BLOQUEADA").upper()
    player = str(homologacao.get("player") or "").strip().upper()
    propostas = {str(p.get("regra_id") or ""): p for p in listar_propostas()}
    proposta = propostas.get(rid) or {}
    etapas = list(proposta.get("etapas") or [])
    checkpoints = [e for e in etapas if str(e.get("responsavel") or "").upper() == "CHECKPOINT_HUMANO"]
    if modo not in {"ASSISTIDA", "AUTOMATICA"}:
        estado = "AGUARDANDO_AUTORIZACAO"
    elif not proposta:
        estado = "AGUARDANDO_PROCEDIMENTO_APRENDIDO"
    else:
        estado = "PREPARACAO_ASSISTIDA_SEM_ENVIO"
    return {"regra_id": rid, "player": player, "operacao": "ABERTURA",
            "estado": estado, "modo": modo, "executavel": False,
            "etapas_aprendidas": len(etapas), "evidencias": proposta.get("evidencias", 0),
            "checkpoints_humanos": checkpoints, "dados_recebidos": sorted(dados),
            "proxima_acao": "Validar procedimento e executor de abertura antes de enviar"}


def avaliar_aberturas_homologadas() -> list[dict]:
    """Inventário do motor de abertura, sem disparos externos."""
    return [avaliar_abertura(h["regra_id"]) for h in listar_homologacoes_mais_recentes()
            if str(h.get("regra_id") or "").startswith("ABERTURA-")]


def autorizar_abertura_assistida(regra_id: str, *, responsavel: str, justificativa: str) -> dict:
    """Libera somente preparação assistida, sem autorização de envio externo."""
    rid = str(regra_id or "").strip()
    responsavel = str(responsavel or "").strip()
    justificativa = str(justificativa or "").strip()
    if not rid.startswith("ABERTURA-"):
        raise ValueError("Regra não pertence ao motor de aberturas.")
    if not responsavel or len(justificativa) < 20:
        raise ValueError("Responsável e justificativa com pelo menos 20 caracteres são obrigatórios.")
    homologacao = estado_regra(rid) or {}
    if homologacao.get("estado") not in {"ATIVA", "EM_OBSERVACAO"}:
        raise ValueError("Abertura não homologada ou suspensa.")
    from ednna.aprendizado_operacional import _garantir_tabela_autorizacoes_motor
    _garantir_tabela_autorizacoes_motor()
    agora = agora_brasil_iso()
    with conectar() as conn:
        conn.execute("""INSERT INTO autorizacoes_motor
            (regra_id,modo,autorizado_por,autorizado_em,observacoes,atualizado_em)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(regra_id) DO UPDATE SET modo=excluded.modo,
              autorizado_por=excluded.autorizado_por, autorizado_em=excluded.autorizado_em,
              observacoes=excluded.observacoes, atualizado_em=excluded.atualizado_em""",
            (rid, "ASSISTIDA", responsavel, agora,
             "Motor de abertura: somente preparação assistida; sem envio externo. " + justificativa, agora))
    return avaliar_abertura(rid)
