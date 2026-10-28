"""Cross-process Redmine inventory reuse for read-only MySQL synchronization.

Only a successful remote listing is cached. Advisory flock serializes refresh
across independent Azure processes; cached data never authorizes VR01 actions.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from pathlib import Path

CACHE = Path(os.getenv("EDDY_REDMINE_INVENTORY_CACHE", "/home/data/eddy_redmine_inventory.json"))
MAX_AGE_SECONDS = 90


def confirmed_inventory_for_mysql(fetch, *, now=None):
    """Reuse recent confirmed inventory exclusively for observational MySQL sync."""
    clock = time.time if now is None else now
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(str(CACHE) + ".lock", "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                cached = json.loads(CACHE.read_text(encoding="utf-8"))
                age = clock() - float(cached["confirmed_at"])
                if (0 <= age <= MAX_AGE_SECONDS and cached.get("fonte") == "redmine"
                        and isinstance(cached.get("chamados"), list) and cached["chamados"]):
                    return {"confirmado": True, "chamados": cached["chamados"],
                            "fonte": "redmine_cache_confirmado", "idade_s": round(age, 2),
                            "somente_observacao": True}
            except (OSError, ValueError, KeyError, TypeError):
                pass
            result = fetch()
            if (result.get("confirmado") is True and result.get("fonte") == "redmine"
                    and isinstance(result.get("chamados"), list) and result["chamados"]):
                payload = {"confirmed_at": clock(), "fonte": "redmine",
                           "chamados": result["chamados"]}
                fd, tmp = tempfile.mkstemp(dir=str(CACHE.parent), prefix=".eddy-inventory-")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False)
                    os.replace(tmp, CACHE)
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
            return result
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
