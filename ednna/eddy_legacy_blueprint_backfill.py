"""Read-only migration of verified Blueprint evidence from historical EDNNA SQLite.

The legacy database is never initialized or modified. A missing file or table
is normal on fresh deployments. Client labels must match exactly.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ednna.armazenamento import obter_caminho_banco
from ednna.eddy_client_identity import _cnpj_values, _norm


def evidencias_legadas(caminho=None, *, clientes=None):
    path = Path(caminho) if caminho is not None else obter_caminho_banco()
    if not path.is_file():
        return {}
    allowed = set(clientes) if clientes is not None else None
    result = {}
    # Immutable mode prevents writes to the historical SQLite database.
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True, timeout=3) as db:
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"blueprint_documentos", "blueprint_linhas"} <= tables:
            return {}
        docs = db.execute(
            "SELECT id, cliente, chamado_id FROM blueprint_documentos").fetchall()
        for doc_id, cliente, bp_id in docs:
            cliente = str(cliente or "").strip()
            if not cliente or (allowed is not None and cliente not in allowed):
                continue
            found = set()
            for (raw,) in db.execute(
                "SELECT dados_json FROM blueprint_linhas WHERE documento_id=?", (doc_id,)):
                try:
                    item = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if not isinstance(item, dict):
                    continue
                for key, value in item.items():
                    if "CNPJ" in _norm(key):
                        found.update(_cnpj_values(value))
            # Only a known Blueprint document with explicit CNPJ is evidence.
            if found and int(bp_id or 0) > 0:
                result.setdefault((cliente, int(bp_id)), set()).update(found)
    return result


def importar_evidencias_legadas(*, caminho=None, clientes=None, registrar=None):
    from ednna.eddy_blueprint_identity_evidence import registrar_bp
    registrar = registrar or registrar_bp
    records = evidencias_legadas(caminho, clientes=clientes)
    # MySQL keys evidence by issue ID; reject conflicting legacy client labels.
    owners = {}
    for cliente, bp_id in records:
        owners.setdefault(bp_id, set()).add(cliente)
    conflicts = {bp_id for bp_id, labels in owners.items() if len(labels) != 1}
    records = {(cliente, bp_id): values for (cliente, bp_id), values in records.items()
               if bp_id not in conflicts}
    for (cliente, bp_id), cnpjs in sorted(records.items()):
        registrar(cliente, bp_id, cnpjs, fonte="EDNNA_SQLITE_LEGADO")
    return {"blueprints": len(records), "conflitos": len(conflicts),
            "clientes": len({cliente for cliente, _ in records})}
