"""Durable, non-dispatchable VR01 proposals built exclusively from MySQL snapshots.

OBSERVACIONAL is deliberately distinct from PENDENTE: the external dispatcher
must never consume an offline proposal as an authorized send.
"""
from __future__ import annotations

import json
import hashlib

from ednna.eddy_vr_action_queue import DDL, criar_intencao
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.mysql_storage import connect

def listar_chamados_vr_mysql() -> tuple[int, ...]:
    """Discover open VR issues from MySQL without a fixed pilot list."""
    from ednna.eddy_vr_origin import identificar_vr
    from ednna.mysql_snapshot_repository import CHAMADO_FIELDS

    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT " + ", ".join(CHAMADO_FIELDS) + " FROM eddy_chamados ORDER BY id")
            rows = cursor.fetchall()
    found = []
    for row in rows:
        issue = dict(zip(CHAMADO_FIELDS, row))
        status = str(issue.get("estado") or "").casefold()
        if any(word in status for word in ("conclu", "fechad", "rejeitad", "cancelad")):
            continue
        if identificar_vr(issue):
            found.append(int(issue["id"]))
    return tuple(found)



def chave_observacional(action_key: str) -> str:
    """Independent namespace: never collide with a dispatchable action key."""
    return hashlib.sha256(f"VR01:OBSERVACIONAL:{action_key}".encode()).hexdigest()


def preparar_intencoes_locais(ids=None) -> dict:
    if ids is None:
        ids = listar_chamados_vr_mysql()
    planned = []
    blocked = []
    for issue_id in ids:
        stored = carregar_snapshot(issue_id)
        if not stored:
            blocked.append({"chamado_id": issue_id, "motivo": "SNAPSHOT_AUSENTE"})
            continue
        payload = stored["chamado"].get("payload_json")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError):
                payload = None
        if not isinstance(payload, dict) or payload.get("id") != issue_id:
            blocked.append({"chamado_id": issue_id, "motivo": "SNAPSHOT_INVALIDO"})
            continue
        journals = [
            {"notes": row.get("notas") or "", "created_on": row.get("criado_em")}
            for row in stored.get("journals", [])
        ]
        proposal = criar_intencao(payload, journals)
        if proposal["situacao"] == "PENDENTE":
            planned.append(proposal)
        else:
            blocked.append({"chamado_id": issue_id, "motivo": proposal["situacao"]})
    # A DB error must fail the cycle: do not report persisted intents on failure.
    inseridas = 0
    existentes = 0
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(DDL)
            for item in planned:
                cursor.execute(
                    """INSERT IGNORE INTO eddy_vr01_action_queue
                    (action_key, chamado_id, redmine_updated_on, etapa, acao, destino, situacao)
                    VALUES (%s,%s,%s,%s,%s,%s,'OBSERVACIONAL')""",
                    (chave_observacional(item["action_key"]),) + tuple(
                        item[k] for k in ("chamado_id", "redmine_updated_on",
                                       "etapa", "acao", "destino")
                    ),
                )
                inseridas += cursor.rowcount
                existentes += int(cursor.rowcount == 0)
    return {
        "estado": "PROPOSTAS_OBSERVACIONAIS_PERSISTIDAS",
        "avaliados": len(ids),
        "propostas": len(planned),
        "inseridas": inseridas,
        "ja_existentes": existentes,
        "bloqueados": blocked,
        "situacao_fila": "OBSERVACIONAL",
        "acoes_externas_autorizadas": False,
        "envios_realizados": 0,
        "redmine_escritas": 0,
    }
