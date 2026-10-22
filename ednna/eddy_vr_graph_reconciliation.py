"""Reconcile VR01 MySQL evidence with existing Microsoft Graph Sent Items.

Read-only with respect to external services. A message found in Sent Items
is evidence of a historical send, not permission to send another one.
"""
from __future__ import annotations

import hashlib
import json
import os
from ednna.mysql_storage import connect
from ednna.email_sender import listar_emails_enviados_por_chamado

def reconciliar_envios_vr01(chamado_ids: list[int], *, buscar=None) -> dict:
    lookup = buscar or listar_emails_enviados_por_chamado
    mailbox = str(os.getenv("EDNNA_EMAIL_FROM") or "").strip()
    if not mailbox:
        return {"estado": "BLOQUEADO_CAIXA_NAO_CONFIGURADA", "consultados": 0, "evidencias": 0}
    ids = sorted(set(int(x) for x in chamado_ids if int(x) > 0))
    observed = []
    errors = []
    for cid in ids:
        try:
            items = lookup(remetente=mailbox, chamado_id=cid)
            for item in items:
                mid = str(item.get("internetMessageId") or item.get("id") or "").strip()
                if not mid or not item.get("sentDateTime"):
                    continue
                digest = hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()
                observed.append((cid, mid[:191], digest))
        except Exception as exc:
            errors.append({"chamado_id": cid, "erro": type(exc).__name__})
    if errors:
        # Never mark a partial mailbox scan as complete.
        return {"estado": "PARCIAL_SEM_GRAVACAO", "consultados": len(ids),
                "evidencias": 0, "erros": errors}
    with connect() as conn:
        with conn.cursor() as cursor:
            for cid, mid, digest in observed:
                cursor.execute(
                    """INSERT IGNORE INTO eddy_external_evidence
                       (source, external_id, chamado_id, regra_id, evidence_type, payload_sha256)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    ("GRAPH", mid, cid, "VR01", "SENT_ITEMS", digest),
                )
    return {"estado": "EVIDENCIAS_RECONCILIADAS", "consultados": len(ids),
            "evidencias": len(observed), "envios_realizados": 0}
