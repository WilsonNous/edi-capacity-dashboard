"""VR01 inbox evidence reconciliation. No external send or automatic closure."""
from __future__ import annotations

import hashlib
import json
import os
from ednna.mysql_storage import connect
from ednna.email_sender import localizar_resposta_por_chamado

def reconciliar_respostas_vr01(chamado_ids: list[int], *, buscar=None) -> dict:
    lookup = buscar or localizar_resposta_por_chamado
    mailbox = str(os.getenv("EDNNA_EMAIL_FROM") or "").strip()
    if not mailbox:
        return {"estado": "BLOQUEADO_CAIXA_NAO_CONFIGURADA", "consultados": 0, "respostas": 0}
    ids = sorted(set(int(x) for x in chamado_ids if int(x) > 0))
    observed = []
    errors = []
    for cid in ids:
        try:
            item = lookup(caixa_postal=mailbox, chamado_id=cid)
            if not item:
                continue
            mid = str(item.get("internetMessageId") or item.get("id") or "").strip()
            when = str(item.get("receivedDateTime") or "").strip()
            if not mid or not when:
                continue
            digest = hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()
            observed.append((cid, mid[:191], digest))
        except Exception as exc:
            errors.append({"chamado_id": cid, "erro": type(exc).__name__})
    if errors:
        return {"estado": "PARCIAL_SEM_GRAVACAO", "consultados": len(ids),
                "respostas": 0, "erros": errors}
    with connect() as conn:
        with conn.cursor() as cursor:
            for cid, mid, digest in observed:
                cursor.execute(
                    """INSERT IGNORE INTO eddy_external_evidence
                       (source, external_id, chamado_id, regra_id, evidence_type, payload_sha256)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    ("GRAPH", mid, cid, "VR01", "INBOX_REPLY", digest),
                )
            # A reply may change the next action; require Redmine/history review
            # before dispatch. Never interpret a reply as an authorization to close.
            for cid in sorted({cid for cid, _, _ in observed}):
                cursor.execute(
                    "UPDATE eddy_vr01_action_queue "
                    "SET situacao='REVISAR_RESPOSTA_RECEBIDA' "
                    "WHERE chamado_id=%s AND situacao='PENDENTE'",
                    (cid,),
                )
    return {"estado": "RESPOSTAS_RECONCILIADAS", "consultados": len(ids),
            "respostas": len(observed), "envios_realizados": 0, "redmine_escritas": 0}
