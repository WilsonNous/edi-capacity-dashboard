"""Conservative readiness guard for operational state, independent of legacy imports."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def persistencia_operacional_disponivel() -> bool:
    """Fail closed until MySQL operational state is migrated and reconciled."""
    if os.getenv("EDDY_DB_ENGINE", "sqlite").strip().lower() == "mysql":
        return False
    path = Path(os.getenv("EDNNA_DB_PATH", "/home/data/ednna.db"))
    if not path.is_file():
        return False
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as conn:
            result = conn.execute("PRAGMA quick_check(1)").fetchone()
            return bool(result and result[0] == "ok")
    except (sqlite3.Error, OSError, ValueError):
        return False
