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
