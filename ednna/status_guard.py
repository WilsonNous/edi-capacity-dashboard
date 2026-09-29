from __future__ import annotations
import unicodedata

# Somente estados cuja semântica terminal foi comprovada na operação Netunna.
# Não ampliar esta lista por similaridade sem validar o catálogo real do Redmine.
ESTADOS_TERMINAIS = {
    "REJEITADA", "REJEITADO",
    "CONCLUIDO", "CONCLUIDA",
    "CANCELADO", "CANCELADA",
    "FECHADO", "FECHADA",
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
    from painel_cache import circuit_breaker_ativo
    from ednna.observabilidade import log_event

    # v3.34.3 — o pre-flight continua fail-safe, mas não fura o circuit breaker.
    # Se a origem está em cooldown, bloquear é mais seguro do que criar uma tempestade
    # de probes concorrentes que prolonga a indisponibilidade do Redmine.
    if circuit_breaker_ativo():
        registrar_auditoria_preflight(chamado_id, "BLOQUEADO", "", "REDMINE_CIRCUIT_BREAKER_ATIVO")
        log_event("SEGURANCA", "Pre-flight bloqueado: Redmine em cooldown", nivel="BLOCKED",
                  chamado_id=chamado_id, detalhe="circuit_breaker=ABERTO", dedup_seconds=120)
        return {"ok":False,"bloquear":True,"motivo":"REDMINE_CIRCUIT_BREAKER_ATIVO",
                "erro":"Circuit breaker global do Redmine ativo.","estado":""}
    try:
        issue=buscar_detalhes_chamado(
            int(chamado_id), consulta_pontual=False, force_refresh=True, timeout=(8,20), tentativas=2
        )
    except Exception as exc:
        registrar_auditoria_preflight(chamado_id, "BLOQUEADO", "", "REDMINE_PREFLIGHT_INDISPONIVEL")
        log_event("SEGURANCA", "Pre-flight bloqueado: Redmine indisponível", nivel="BLOCKED",
                  chamado_id=chamado_id, detalhe=f"{type(exc).__name__}: {exc}", dedup_seconds=120)
        return {"ok":False,"bloquear":True,"motivo":"REDMINE_PREFLIGHT_INDISPONIVEL",
                "erro":f"{type(exc).__name__}: {exc}","estado":""}
    if not issue:
        registrar_auditoria_preflight(chamado_id, "BLOQUEADO", "", "CHAMADO_NAO_LOCALIZADO")
        return {"ok":False,"bloquear":True,"motivo":"CHAMADO_NAO_LOCALIZADO","estado":""}
    estado=estado_issue(issue)
    if estado_terminal_nome(estado):
        resultado={"ok":True,"bloquear":True,"motivo":"ESTADO_TERMINAL","estado":estado,"issue":issue}
        registrar_auditoria_preflight(chamado_id, "BLOQUEADO", estado, "ESTADO_TERMINAL")
        log_event("SEGURANCA", "Pre-flight bloqueado: estado terminal", nivel="BLOCKED",
                  chamado_id=chamado_id, detalhe=f"estado={estado}", dedup_seconds=300)
        return resultado
    registrar_auditoria_preflight(chamado_id, "LIBERADO", estado, "ATIVO")
    return {"ok":True,"bloquear":False,"motivo":"ATIVO","estado":estado,"issue":issue}

def registrar_auditoria_preflight(chamado_id: int, resultado: str, estado: str = "", motivo: str = "") -> None:
    """Persiste a decisão de segurança sem depender do journal do chamado."""
    try:
        from ednna.acompanhamento_acoes import _conectar, _iso, _agora
        with _conectar() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS auditoria_preflight (
                id INTEGER PRIMARY KEY AUTOINCREMENT, chamado_id INTEGER NOT NULL,
                resultado TEXT NOT NULL, estado_redmine TEXT, motivo TEXT, criado_em TEXT NOT NULL
            )""")
            conn.execute("INSERT INTO auditoria_preflight(chamado_id,resultado,estado_redmine,motivo,criado_em) VALUES(?,?,?,?,?)",
                         (int(chamado_id), str(resultado), str(estado or ""), str(motivo or ""), _iso(_agora())))
    except Exception as exc:
        print(f"[EDNNA] Auditoria pre-flight falhou | chamado={chamado_id} | {type(exc).__name__}: {exc}", flush=True)

def validar_efeito_externo(chamado_id: int, acao: str) -> dict:
    """Barreira global imediatamente antes de qualquer efeito externo conhecido."""
    resultado = preflight_chamado_ativo(int(chamado_id))
    if resultado.get("bloquear"):
        if resultado.get("motivo") == "ESTADO_TERMINAL":
            encerrar_acompanhamento_terminal(int(chamado_id), resultado.get("estado") or "")
        registrar_auditoria_preflight(chamado_id, "BLOQUEADO", resultado.get("estado") or "", f"{acao}:{resultado.get('motivo')}")
    return resultado

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
