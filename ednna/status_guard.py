from __future__ import annotations
import unicodedata

ESTADOS_TERMINAIS = {
    "REJEITADA","REJEITADO","CONCLUIDO","CONCLUIDA","FECHADO","FECHADA",
    "CANCELADO","CANCELADA","RESOLVIDO","RESOLVIDA"
}

def _norm(valor) -> str:
    txt=str(valor or "").strip().upper()
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))

def estado_terminal_nome(valor) -> bool:
    return _norm(valor) in ESTADOS_TERMINAIS

def estado_issue(issue: dict) -> str:
    status=issue.get("status") or {}
    return str(status.get("name") if isinstance(status,dict) else status or "").strip()

def preflight_chamado_ativo(chamado_id: int) -> dict:
    """Consulta pontual imediatamente antes de uma atuação externa.
    Falha de consulta é bloqueio seguro: não enviar com estado desconhecido.
    """
    from redmine_api import buscar_detalhes_chamado
    try:
        issue=buscar_detalhes_chamado(
            int(chamado_id), consulta_pontual=True, force_refresh=True, timeout=(8,20), tentativas=2
        )
    except Exception as exc:
        return {"ok":False,"bloquear":True,"motivo":"REDMINE_PREFLIGHT_INDISPONIVEL",
                "erro":f"{type(exc).__name__}: {exc}","estado":""}
    if not issue:
        return {"ok":False,"bloquear":True,"motivo":"CHAMADO_NAO_LOCALIZADO","estado":""}
    estado=estado_issue(issue)
    if estado_terminal_nome(estado) or bool(issue.get("closed_on")):
        return {"ok":True,"bloquear":True,"motivo":"ESTADO_TERMINAL","estado":estado,"issue":issue}
    return {"ok":True,"bloquear":False,"motivo":"ATIVO","estado":estado,"issue":issue}

def encerrar_acompanhamento_terminal(chamado_id: int, estado_redmine: str="") -> None:
    """Retira chamado terminal das filas de acompanhamento/follow-up sem apagar auditoria."""
    try:
        from ednna.acompanhamento_acoes import _conectar, _iso, _agora, inicializar_acompanhamento
        inicializar_acompanhamento()
        with _conectar() as conn:
            conn.execute("""UPDATE acoes_operacionais
                SET estado='IGNORADO_ESTADO_TERMINAL',
                    prazo_resposta_em=NULL,
                    observacao=?,
                    atualizado_em=?
                WHERE chamado_id=? AND estado NOT IN ('RESPOSTA_RECEBIDA','CONCLUIDO')""",
                (f"Redmine em estado terminal: {estado_redmine or 'não ativo'}", _iso(_agora()), int(chamado_id)))
    except Exception as exc:
        print(f"[EDNNA] Estado terminal | limpeza acompanhamento falhou | chamado={chamado_id} | {type(exc).__name__}: {exc}", flush=True)
