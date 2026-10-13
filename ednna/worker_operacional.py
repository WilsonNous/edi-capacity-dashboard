"""Worker dedicado do monitor EDI. Nunca inicia pela API ou interface."""
from __future__ import annotations

import signal

from ednna import monitor_respostas


def main() -> None:
    def parar(_signum, _frame):
        monitor_respostas._STOP.set()

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    monitor_respostas._loop()


if __name__ == "__main__":
    main()
