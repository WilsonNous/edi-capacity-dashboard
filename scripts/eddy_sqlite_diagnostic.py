"""Read-only EDDY SQLite health diagnostic; never repairs or removes data."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def diagnosticar_sqlite(path: str) -> dict:
    file = Path(path)
    result = {"arquivo": str(file), "existe": file.exists(), "status": "AUSENTE"}
    if not file.exists():
        return result
    result["tamanho_bytes"] = file.stat().st_size
    try:
        # URI read-only; immutable=1 is deliberately NOT used so WAL remains visible.
        from urllib.parse import quote
        uri = "file:" + quote(str(file.resolve())) + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=3) as conn:
            row = conn.execute("PRAGMA quick_check(1)").fetchone()
        result["status"] = "INTEGRO" if row and row[0] == "ok" else "CORROMPIDO"
    except (sqlite3.DatabaseError, OSError) as exc:
        result["status"] = "INACESSIVEL_OU_CORROMPIDO"
        result["erro_tipo"] = type(exc).__name__
    return result


if __name__ == "__main__":
    path = os.getenv("EDNNA_DB_PATH") or ("/home/data/ednna.db" if os.getenv("WEBSITE_INSTANCE_ID") else "data/ednna.db")
    print("[EDDY-SQLITE-DIAG] " + json.dumps(diagnosticar_sqlite(path), ensure_ascii=False), flush=True)
