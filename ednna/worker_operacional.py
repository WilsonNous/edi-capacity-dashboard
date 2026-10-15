"""Worker operacional dedicado: monitor e follow-ups independentes da UI/API."""
from __future__ import annotations

import os
import signal
import threading

from ednna import monitor_respostas
from ednna.worker_followups import loop_followups


def main() -> None:
    def parar(_signum, _frame):
        monitor_respostas._STOP.set()

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    if os.getenv("EDDY_FOLLOWUP_WORKER_ENABLED", "false").strip().lower() in {"true", "1", "yes", "on"}:
        thread = threading.Thread(
            target=loop_followups, args=(monitor_respostas._STOP,),
            name="eddy-followups", daemon=True,
        )
        thread.start()
    else:
        print("[EDDY] Follow-up | worker desabilitado", flush=True)
    monitor_respostas._loop()


if __name__ == "__main__":
    main()
