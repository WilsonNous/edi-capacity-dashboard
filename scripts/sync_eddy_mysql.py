"""Sincronização observacional Redmine -> MySQL; sem efeitos externos.

Nunca interpreta um snapshot de contingência como resposta atual do Redmine.
A carteira MySQL é atualizada somente após refresh remoto confirmado.
"""
from __future__ import annotations
import argparse
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ednna.mysql_panel_bridge import importar_snapshot_painel_mysql, extrair_snapshot_painel

BR = ZoneInfo("America/Sao_Paulo")


def sincronizar_uma_vez(*, painel="/home/data/painel.db") -> dict:
    from redmine_api import buscar_chamados_projetos, obter_diagnostico_redmine, REDMINE_PROJECT_IDS
    inicio = time.monotonic()
    chamados = buscar_chamados_projetos(
        project_ids=REDMINE_PROJECT_IDS, status_id="open",
        completar_custom_fields=True, force_refresh=True,
    )
    diagnostico = obter_diagnostico_redmine()
    if diagnostico.get("fonte_dados") != "redmine":
        raise RuntimeError("Redmine não confirmou refresh remoto; MySQL preservado")
    if not isinstance(chamados, list) or not chamados:
        raise ValueError("Carteira vazia ou inválida; MySQL preservado")
    if len(chamados) > 500:
        raise ValueError("Carteira excede capacidade do piloto (500); MySQL preservado")
    items, _ = extrair_snapshot_painel(painel)
    ids_redmine = [int(x["id"]) for x in chamados]
    ids_painel = [int(x["id"]) for x in items]
    if len(ids_redmine) != len(set(ids_redmine)) or sorted(ids_redmine) != sorted(ids_painel):
        raise RuntimeError("Snapshot diverge da consulta; MySQL preservado")
    resultado = importar_snapshot_painel_mysql(painel, limite=500, aplicar=True)
    resultado["duracao_total_s"] = round(time.monotonic() - inicio, 3)
    resultado["redmine_confirmado"] = True
    return resultado


def main():
    parser = argparse.ArgumentParser(description="EDDY: sincronização observacional segura")
    parser.add_argument("--painel", default="/home/data/painel.db")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--intervalo", type=int, default=900)
    args = parser.parse_args()
    if args.loop and args.intervalo < 300:
        parser.error("intervalo mínimo: 300 segundos")
    while True:
        try:
            result = sincronizar_uma_vez(painel=args.painel)
            print("[EDDY-MYSQL-SYNC] " + json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(f"[EDDY-MYSQL-SYNC] Falha segura: {type(exc).__name__}: {exc}", flush=True)
            if not args.loop:
                raise SystemExit(1)
        if not args.loop:
            return
        time.sleep(args.intervalo)


if __name__ == "__main__":
    main()
