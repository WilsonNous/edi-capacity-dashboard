"""Safe sync timing helpers: instrumentation only, no database or network calls."""
from __future__ import annotations

from time import perf_counter


class SyncTimings:
    """Collect monotonic stage timings without logging issue payloads or credentials."""

    def __init__(self, clock=perf_counter):
        self._clock = clock
        self._started = clock()
        self._marks = {}
        self._last = self._started

    def mark(self, stage: str) -> float:
        if stage not in ("redmine", "mysql", "mysql_connect", "mysql_write", "mysql_commit"):
            raise ValueError("ETAPA_DESCONHECIDA")
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._marks[stage] = round(self._marks.get(stage, 0.0) + elapsed, 3)
        self._last = now
        return elapsed

    def report(self) -> dict:
        return {"duracao_total_s": round(max(0.0, self._clock() - self._started), 3),
                "etapas_s": dict(self._marks)}
