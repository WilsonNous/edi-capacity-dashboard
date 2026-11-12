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
        return {"estado": "PARCIAL_COM_GRAVACAO" if errors else "EVIDENCIAS_RECONCILIADAS",
            "consultados": len(ids), "evidencias": len(observed),
            "erros": errors, "envios_realizados": 0}
