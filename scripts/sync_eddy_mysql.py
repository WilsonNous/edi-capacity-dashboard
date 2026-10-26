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

from datetime import datetime, timezone
from ednna.mysql_snapshot_repository import salvar_snapshot
from ednna.mysql_storage import connect
from ednna.redmine_resilient_reads import listar_abertos_confirmados

BR = ZoneInfo("America/Sao_Paulo")


def _timestamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def sincronizar_uma_vez(*, painel=None) -> dict:
    """Read confirmed Redmine inventory directly into MySQL; no SQLite bridge.

    The legacy painel parameter is accepted only to avoid breaking old callers.
    It is deliberately never read.
    """
    inicio = time.monotonic()
    inventory = listar_abertos_confirmados()
    duracao_redmine_s = round(time.monotonic() - inicio, 3)
    if not inventory["confirmado"]:
        raise RuntimeError("Redmine não confirmou refresh remoto; MySQL preservado")
    chamados = inventory["chamados"]
    if not isinstance(chamados, list) or not chamados:
        raise ValueError("Carteira vazia ou inválida; MySQL preservado")
    if len(chamados) > 500:
        raise ValueError("Carteira excede capacidade do piloto (500); MySQL preservado")
    ids = [int(x["id"]) for x in chamados]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs duplicados no Redmine; MySQL preservado")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    gravados = 0
    inicio_mysql = time.monotonic()
    with connect() as conn:
      duracao_conexao_mysql_s = round(time.monotonic() - inicio_mysql, 3)
      with conn.cursor() as cursor:
       for issue in chamados:
        row = {
            "id": int(issue["id"]),
            "cliente": None,
            "origem": None,
            "responsavel": (issue.get("assigned_to") or {}).get("name"),
            "projeto": (issue.get("project") or {}).get("name"),
            "tipo": (issue.get("tracker") or {}).get("name"),
            "estado": (issue.get("status") or {}).get("name"),
            "prioridade": (issue.get("priority") or {}).get("name"),
            "assunto": issue.get("subject"),
            "criado_em": _timestamp(issue.get("created_on")),
            "alterado_em": _timestamp(issue.get("updated_on")),
            "tempo_aberto_dias": None,
            "payload_json": issue,
            "sincronizado_em": now,
        }
        salvar_snapshot(row, cursor=cursor)
        gravados += 1
    duracao_mysql_s = round(time.monotonic() - inicio_mysql, 3)
    return {
        "origem": "redmine/status=open", "destino": "mysql",
        "total_origem": len(chamados), "gravados": gravados,
        "journals": "sincronizados apenas pelo fluxo dedicado VR01",
        "automacoes": "suspensas", "modo": "apply",
        "duracao_total_s": round(time.monotonic() - inicio, 3),
        "duracao_redmine_s": duracao_redmine_s,
        "duracao_mysql_s": duracao_mysql_s,
        "duracao_conexao_mysql_s": duracao_conexao_mysql_s,
        "redmine_confirmado": True,
    }


def main():
    parser = argparse.ArgumentParser(description="EDDY: sincronização observacional segura")
    parser.add_argument("--painel", default=None, help="Legado: ignorado; origem direta Redmine")
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
