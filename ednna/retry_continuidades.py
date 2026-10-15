"""Pendencias de enriquecimento Redmine com retry controlado e cursor rotativo."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

CHAVE_PENDENCIAS = "eddy:continuidade:reconstrucao:pendentes"
INTERVALO_MINUTOS = 15


def _agora():
    return datetime.now(timezone.utc)


def _ler() -> dict:
    from painel_cache import obter_metadado_json
    dados = obter_metadado_json(CHAVE_PENDENCIAS, {})
    return dados if isinstance(dados, dict) else {}


def selecionar_com_pendencias(ids: list[int], limite: int, cursor_chave: str) -> list[int]:
    """Prioriza pendencias vencidas; completa com rotacao; falha de DB nao libera envio."""
    from ednna.lotes_continuidade import selecionar_persistido
    candidatos = sorted({int(x) for x in ids if int(x) > 0})
    tamanho = max(0, int(limite))
    if not tamanho:
        return []
    try:
        pendencias = _ler()
    except Exception as exc:
        print(f"[EDDY] Continuidade | pendencias indisponiveis | erro={type(exc).__name__}", flush=True)
        pendencias = {}
    agora = _agora()
    vencidos = []
    em_espera = set()
    for cid in candidatos:
        prazo = pendencias.get(str(cid))
        if not prazo:
            continue
        try:
            data = datetime.fromisoformat(str(prazo))
            if data.tzinfo is None:
                data = data.replace(tzinfo=timezone.utc)
            if data <= agora:
                vencidos.append(cid)
            else:
                em_espera.add(cid)
        except (ValueError, TypeError):
            vencidos.append(cid)
    # A rotacao segue funcionando para os demais chamados.
    novos = selecionar_persistido([cid for cid in candidatos if cid not in em_espera and cid not in vencidos], tamanho, cursor_chave)
    return (vencidos[:tamanho] + [cid for cid in novos if cid not in vencidos])[:tamanho]


def registrar_resultados(resultados: list[dict]) -> dict:
    """Persistir pendencias e remover apenas resultados comprovadamente concluidos."""
    from painel_cache import salvar_metadado_json
    dados = _ler()
    proxima = (_agora() + timedelta(minutes=INTERVALO_MINUTOS)).isoformat()
    for item in resultados:
        cid = int(item.get("chamado_id") or 0)
        if cid <= 0:
            continue
        if item.get("ok"):
            dados.pop(str(cid), None)
        else:
            dados[str(cid)] = proxima
    salvar_metadado_json(CHAVE_PENDENCIAS, dados)
    return {"pendentes_persistidos": len(dados), "lote": len(resultados)}
