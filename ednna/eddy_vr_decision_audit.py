"""Persist immutable, idempotent VR decision audits. No operational side effects."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone

from ednna.eddy_vr_rule import avaliar_vr
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.mysql_storage import connect


def preparar_decisao(chamado_id: int) -> dict:
    snapshot = carregar_snapshot(chamado_id)
    if snapshot is None:
        raise ValueError(f"Snapshot ausente: {chamado_id}")
    decision = avaliar_vr(snapshot["chamado"], snapshot["journals"])
    payload = json.dumps({"snapshot": snapshot, "decision": decision},
                         sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {"chamado_id": chamado_id, "digest": digest, "decisao": decision,
            "snapshot": snapshot}


def registrar_decisao(chamado_id: int) -> dict:
    """Append once per identical snapshot and decision; requires pre-applied DDL."""
    item = preparar_decisao(chamado_id)
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO eddy_vr_decisoes
                   (chamado_id, digest, decisao_json, snapshot_json, criado_em)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE digest = digest""",
                (item["chamado_id"], item["digest"],
                 json.dumps(item["decisao"], ensure_ascii=False),
                 json.dumps(item["snapshot"], ensure_ascii=False, default=str),
                 datetime.now(timezone.utc).replace(tzinfo=None)),
            )
    return {"chamado_id": item["chamado_id"], "digest": item["digest"],
            "decisao": item["decisao"], "execucao_externa": False}
