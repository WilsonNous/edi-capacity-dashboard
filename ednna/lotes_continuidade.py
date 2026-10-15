"""Rotacao persistente de lotes legados, sem alterar tickets ou enviar e-mails."""
from __future__ import annotations


def selecionar_lote_rotativo(ids: list[int], limite: int, cursor: int | None = None) -> list[int]:
    """Ordem estavel; retoma apos ultimo ID, incluindo wrap-around."""
    unicos = sorted({int(x) for x in ids if int(x) > 0})
    tamanho = max(0, int(limite))
    if not unicos or not tamanho:
        return []
    inicio = next((i for i, cid in enumerate(unicos) if cid > int(cursor or 0)), 0)
    return [unicos[(inicio + i) % len(unicos)] for i in range(min(tamanho, len(unicos)))]


def selecionar_persistido(ids: list[int], limite: int, chave: str) -> list[int]:
    """Falha do cache nao impede diagnostico local; cursor so avanca apos lote."""
    try:
        from painel_cache import obter_metadado
        cursor = int(obter_metadado(chave) or 0)
    except (ValueError, TypeError, OSError):
        cursor = 0
    return selecionar_lote_rotativo(ids, limite, cursor)


def confirmar_lote(chave: str, ids: list[int]) -> None:
    """Checkpoint de progresso, nao evidencia de atuacao externa."""
    if not ids:
        return
    try:
        from painel_cache import salvar_metadado
        salvar_metadado(chave, str(int(ids[-1])))
    except Exception as exc:
        print(f"[EDDY] Continuidade | cursor nao persistido | chave={chave} | erro={type(exc).__name__}", flush=True)
