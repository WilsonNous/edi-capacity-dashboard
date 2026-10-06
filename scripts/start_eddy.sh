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

python - <<'PY'
import time, urllib.request
targets = [
    ("Streamlit", "http://127.0.0.1:8501/_stcore/health", {200}),
    ("Intelligence API", "http://127.0.0.1:8001/api/intelligence/handshake", {200, 401, 422}),
]
for name, url, accepted in targets:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
        except urllib.error.HTTPError as exc:
            if exc.code in accepted:
                print(f"[EDDY] {name} pronto: HTTP {exc.code}", flush=True)
                break
        except Exception:
            pass
        else:
            print(f"[EDDY] {name} pronto", flush=True)
            break
        time.sleep(1)
    else:
        raise SystemExit(f"[EDDY] Timeout aguardando {name}")
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
