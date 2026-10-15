"""Ciclo independente de follow-ups, sem envio pela UI/API."""
from __future__ import annotations

import os
import time


def executar_ciclo_followups() -> dict:
    from ednna.followup_engine import avaliar_followups, executar_followup, followup_automatico
    inicio = time.monotonic()
    avaliacao = avaliar_followups()
    limite = max(1, min(10, int(os.getenv("EDDY_FOLLOWUP_BATCH_SIZE", "3"))))
    elegiveis = [
        item for item in avaliacao.get("itens", [])
        if item.get("estado_followup") == "FOLLOWUP_PRONTO" and followup_automatico(item)
    ][:limite]
    resumo = {"elegiveis": avaliacao.get("automaticos_prontos", 0), "lote": len(elegiveis),
              "sucessos": 0, "bloqueados": 0, "erros": 0}
    print(f"[EDDY] Follow-up | inicio | elegiveis={resumo['elegiveis']} | lote={len(elegiveis)}", flush=True)
    for item in elegiveis:
        try:
            resultado = executar_followup(item)
            ok = bool(resultado.get("ok"))
            resumo["sucessos" if ok else "bloqueados"] += 1
            print(f"[EDDY] Follow-up | chamado={item.get('chamado_id')} | estado={resultado.get('estado', 'EXECUTADO' if ok else 'BLOQUEADO')} | ok={ok}", flush=True)
        except Exception as exc:
            resumo["erros"] += 1
            print(f"[EDDY] Follow-up | chamado={item.get('chamado_id')} | erro={type(exc).__name__}: {str(exc)[:200]}", flush=True)
    resumo["duracao_s"] = round(time.monotonic() - inicio, 2)
    print(f"[EDDY] Follow-up | ciclo concluido | {resumo}", flush=True)
    return resumo


def loop_followups(stop) -> None:
    intervalo = max(300, int(os.getenv("EDDY_FOLLOWUP_INTERVAL_SECONDS", "900")))
    atraso = max(10, int(os.getenv("EDDY_FOLLOWUP_INITIAL_DELAY_SECONDS", "60")))
    print(f"[EDDY] Follow-up | worker iniciado | atraso={atraso}s | intervalo={intervalo}s", flush=True)
    if stop.wait(atraso):
        return
    while not stop.is_set():
        try:
            executar_ciclo_followups()
        except Exception as exc:
            print(f"[EDDY] Follow-up | falha ciclo | {type(exc).__name__}: {str(exc)[:200]}", flush=True)
        stop.wait(intervalo)
