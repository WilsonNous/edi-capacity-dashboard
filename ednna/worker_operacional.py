"""Worker operacional dedicado: monitor e follow-ups independentes da UI/API."""
from __future__ import annotations

import os
import signal
import threading

from ednna import monitor_respostas
from ednna.worker_followups import loop_followups


def loop_redmine_outbox(stop: threading.Event) -> None:
    """Reconciliador independente: não bloqueia leitura de e-mail nem follow-ups."""
    from ednna.redmine_outbox import reconciliar_redmine_pendentes
    intervalo = max(300, int(os.getenv("EDDY_REDMINE_OUTBOX_INTERVAL_SECONDS", "3600")))
    atraso = max(10, int(os.getenv("EDDY_REDMINE_OUTBOX_INITIAL_DELAY_SECONDS", "90")))
    if stop.wait(atraso):
        return
    while not stop.is_set():
        try:
            resultado = reconciliar_redmine_pendentes(max(1, int(os.getenv("EDDY_REDMINE_OUTBOX_BATCH_SIZE", "10"))))
            if resultado.get("consultados"):
                print(f"[EDDY] Outbox Redmine | {resultado}", flush=True)
        except Exception as exc:
            print(f"[EDDY] Outbox Redmine | erro={type(exc).__name__}: {exc}", flush=True)
        stop.wait(intervalo)


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
    if os.getenv("EDDY_REDMINE_OUTBOX_WORKER_ENABLED", "true").strip().lower() in {"true", "1", "yes", "on"}:
        threading.Thread(target=loop_redmine_outbox, args=(monitor_respostas._STOP,), name="eddy-redmine-outbox", daemon=True).start()
    monitor_respostas._loop()


if __name__ == "__main__":
    main()
