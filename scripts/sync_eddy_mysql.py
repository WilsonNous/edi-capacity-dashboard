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
from ednna.mysql_snapshot_repository import _upsert, CHAMADO_FIELDS
from ednna.mysql_storage import connect
from ednna.mysql_redmine_catalog import mapa_persistido
from ednna.redmine_resilient_reads import listar_abertos_confirmados
from ednna.redmine_shared_inventory import confirmed_inventory_for_mysql

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
    inventory = confirmed_inventory_for_mysql(listar_abertos_confirmados)
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
    # Resolve client option IDs once per cycle, never guess unknown names.
    mapa_clientes = mapa_persistido(1)
    gravados = 0
    clientes_nao_resolvidos = set()
    inicio_mysql = time.monotonic()
    duracao_preparacao_mysql_s = 0.0
    duracao_upsert_mysql_s = 0.0
    inicio_fechamento_mysql = None
    with connect() as conn:
      duracao_conexao_mysql_s = round(time.monotonic() - inicio_mysql, 3)
      with conn.cursor() as cursor:
       placeholders = ", ".join(["%s"] * len(ids))
       cursor.execute(f"SELECT id, payload_json FROM eddy_chamados WHERE id IN ({placeholders}) FOR UPDATE", tuple(ids))
       anteriores = {int(i): payload for i, payload in cursor.fetchall()}
       for issue in chamados:
        inicio_preparacao = time.monotonic()
        valores = next((f.get("value") for f in issue.get("custom_fields", []) if str(f.get("id")) == "1"), None)
        codigos = [str(v).strip() for v in (valores if isinstance(valores, list) else [valores]) if v not in (None, "")]
        nomes = [mapa_clientes.get(c) for c in codigos]
        if any(nome is None for nome in nomes):
            clientes_nao_resolvidos.update(c for c in codigos if c not in mapa_clientes)
        cliente = nomes[0] if len(nomes) == 1 and nomes[0] else None
        row = {
            "id": int(issue["id"]),
            "cliente": cliente,
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
        duracao_preparacao_mysql_s += time.monotonic() - inicio_preparacao
        inicio_upsert = time.monotonic()
        anterior = anteriores.get(row["id"])
        if anterior:
            try:
                payload_anterior = json.loads(anterior) if isinstance(anterior, str) else anterior
            except (TypeError, ValueError):
                payload_anterior = {}
            if (isinstance(payload_anterior, dict) and payload_anterior.get("_eddy_journals_completos") is True
                and str(payload_anterior.get("updated_on") or "") == str(issue.get("updated_on") or "")):
                row["payload_json"] = payload_anterior
        _upsert(cursor, "eddy_chamados", CHAMADO_FIELDS, row)
        duracao_upsert_mysql_s += time.monotonic() - inicio_upsert
        gravados += 1
      inicio_fechamento_mysql = time.monotonic()
    fim_mysql = time.monotonic()
    duracao_mysql_s = round(fim_mysql - inicio_mysql, 3)
    duracao_fechamento_mysql_s = round(fim_mysql - inicio_fechamento_mysql, 3)
    return {
        "origem": "redmine/status=open", "destino": "mysql",
        "total_origem": len(chamados), "gravados": gravados,
        "clientes_nao_resolvidos": sorted(clientes_nao_resolvidos),
        "journals": "sincronizados apenas pelo fluxo dedicado VR01",
        "automacoes": "suspensas", "modo": "apply",
        "duracao_total_s": round(time.monotonic() - inicio, 3),
        "duracao_redmine_s": duracao_redmine_s,
        "duracao_mysql_s": duracao_mysql_s,
        "duracao_conexao_mysql_s": duracao_conexao_mysql_s,
        "duracao_preparacao_mysql_s": round(duracao_preparacao_mysql_s, 3),
        "duracao_upsert_mysql_s": round(duracao_upsert_mysql_s, 3),
        "duracao_fechamento_mysql_s": duracao_fechamento_mysql_s,
        "redmine_confirmado": True,
        "origem_confirmacao": inventory.get("fonte"),
        "idade_confirmacao_s": inventory.get("idade_s", 0),
        "cache_apenas_observacional": inventory.get("somente_observacao", False),
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
