"""Telemetria agregada de conectividade Redmine; sem dados de chamados ou credenciais."""
from __future__ import annotations

from collections import Counter, deque
from threading import Lock
from time import monotonic

_LOCK = Lock()
_EVENTOS = deque(maxlen=200)
_ULTIMO_LOG = 0.0


def registrar_resultado(tipo: str, duracao_s: float, *, janela_s: int = 300, intervalo_log_s: int = 60) -> dict:
    """Janela deslizante e resumo periódico; jamais altera o circuit breaker."""
    global _ULTIMO_LOG
    agora = monotonic()
    with _LOCK:
        _EVENTOS.append((agora, str(tipo), max(0.0, float(duracao_s))))
        while _EVENTOS and agora - _EVENTOS[0][0] > janela_s:
            _EVENTOS.popleft()
        contagem = Counter(evento[1] for evento in _EVENTOS)
        duracoes_ok = [evento[2] for evento in _EVENTOS if evento[1] == "OK"]
        total = len(_EVENTOS)
        resumo = {
            "janela_s": janela_s,
            "total": total,
            "sucessos": contagem.get("OK", 0),
            "timeout_conexao": contagem.get("TIMEOUT_CONEXAO", 0),
            "timeout_resposta": contagem.get("TIMEOUT_RESPOSTA", 0),
            "erro_conexao": contagem.get("ERRO_CONEXAO", 0),
            "taxa_sucesso_pct": round(100 * contagem.get("OK", 0) / total, 1) if total else 0.0,
            "latencia_ok_media_s": round(sum(duracoes_ok) / len(duracoes_ok), 2) if duracoes_ok else None,
        }
        emitir = agora - _ULTIMO_LOG >= intervalo_log_s
        if emitir:
            _ULTIMO_LOG = agora
    if emitir:
        print(
            "[REDMINE-SAUDE] "
            + " | ".join(f"{chave}={valor}" for chave, valor in resumo.items()),
            flush=True,
        )
    return resumo


def obter_saude_redmine() -> dict:
    """Snapshot local do processo; não é indicador global multi-instância."""
    with _LOCK:
        eventos = list(_EVENTOS)
    agora = monotonic()
    recentes = [x for x in eventos if agora - x[0] <= 300]
    contagem = Counter(x[1] for x in recentes)
    return {"janela_s": 300, "total": len(recentes), "por_tipo": dict(sorted(contagem.items()))}
