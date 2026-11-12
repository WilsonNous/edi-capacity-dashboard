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
        return {"estado": "PARCIAL_COM_GRAVACAO" if errors else "RESPOSTAS_RECONCILIADAS",
            "consultados": len(ids), "respostas": len(observed),
            "erros": errors, "envios_realizados": 0, "redmine_escritas": 0}
