#!/usr/bin/env bash
set -Eeuo pipefail

export PYTHONUNBUFFERED=1
UI_PORT="${EDDY_UI_PORT:-8501}"
API_PORT="${EDDY_API_PORT:-8001}"
PUBLIC_PORT="${PORT:-8000}"

pids=()

shutdown() {
  trap - TERM INT EXIT
  for pid in "${pids[@]:-}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait || true
}
trap shutdown TERM INT EXIT

python -m streamlit run app.py --server.port "$UI_PORT" --server.address 127.0.0.1 &
pids+=("$!")

python -m uvicorn eddy_api.main:app --host 127.0.0.1 --port "$API_PORT" --workers 1 &
pids+=("$!")

export EDDY_READY_UI_URL="http://127.0.0.1:${UI_PORT}/_stcore/health"
export EDDY_READY_API_URL="http://127.0.0.1:${API_PORT}/api/intelligence/handshake"

python - <<'PY'
import os
import time
import urllib.error
import urllib.request

targets = [
    ("Streamlit", os.environ["EDDY_READY_UI_URL"], {200}),
    ("Intelligence API", os.environ["EDDY_READY_API_URL"], {200, 401, 403, 422}),
]

for name, url, accepted in targets:
    deadline = time.time() + 60
    last_detail = "sem resposta"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                code = response.status
            last_detail = f"HTTP {code}"
            if code in accepted:
                print(f"[EDDY] {name} pronto: HTTP {code}", flush=True)
                break
            print(f"[EDDY] {name} ainda não pronto: HTTP {code}", flush=True)
        except urllib.error.HTTPError as exc:
            last_detail = f"HTTP {exc.code}"
            if exc.code in accepted:
                print(f"[EDDY] {name} pronto: HTTP {exc.code}", flush=True)
                break
            print(f"[EDDY] {name} ainda não pronto: HTTP {exc.code}", flush=True)
        except Exception as exc:
            last_detail = f"{type(exc).__name__}: {exc}"
            print(f"[EDDY] {name} aguardando: {last_detail}", flush=True)
        time.sleep(1)
    else:
        raise SystemExit(f"[EDDY] Timeout aguardando {name}; último resultado: {last_detail}")
PY

python -m uvicorn eddy_gateway:app --host 0.0.0.0 --port "$PUBLIC_PORT" --workers 1 &
pids+=("$!")

while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "[EDDY] Processo crítico encerrou: pid=$pid. Encerrando conjunto." >&2
      exit 1
    fi
  done
  sleep 2
done
