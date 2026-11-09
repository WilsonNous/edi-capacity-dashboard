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

# Run the MySQL-native VR01 portfolio, not the legacy SQLite worker.
# Respect explicit Azure settings; production operators can disable any gate.
if [[ "${EDDY_DB_ENGINE:-sqlite}" == "mysql" ]]; then
  export EDNNA_MONITOR_EMAIL_ENABLED=false
  export EDNNA_AUTO_EXECUTE=false
  export EDNNA_FOLLOWUP_AUTO=false
  export EDDY_VR01_OFFLINE_FIRST=false
  export EDDY_MOTORES_OBSERVABILIDADE_ENABLED=false
  export EDDY_VR01_PORTFOLIO_ENABLED="${EDDY_VR01_PORTFOLIO_ENABLED:-true}"
  export EDDY_VR01_PORTFOLIO_INTERNAL_ADVANCE="${EDDY_VR01_PORTFOLIO_INTERNAL_ADVANCE:-true}"
  export EDDY_VR01_EXTERNAL_ENABLED="${EDDY_VR01_EXTERNAL_ENABLED:-true}"
  export EDDY_VR01_REPLY_RECONCILIATION_READY="${EDDY_VR01_REPLY_RECONCILIATION_READY:-true}"
  export EDDY_VR01_AUTO_SEND_PORTAL="${EDDY_VR01_AUTO_SEND_PORTAL:-true}"
  echo "[EDDY] MySQL VR01 operational portfolio enabled; legacy SQLite worker disabled."
fi

EDNNA_MONITOR_EMAIL_ENABLED=false python -m streamlit run app.py --server.port "$UI_PORT" --server.address 127.0.0.1 &
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
    ("Intelligence API", os.environ["EDDY_READY_API_URL"], {200}),
]

for name, url, accepted in targets:
    deadline = time.time() + 60
    last_detail = "sem resposta"
    while time.time() < deadline:
        try:
            headers = {}
            if name == "Intelligence API":
                from eddy_api import CONTRACT_VERSION
                headers["X-EDNNA-Contract-Version"] = CONTRACT_VERSION
                token = os.environ.get("EDDY_INTELLIGENCE_TOKEN", "").strip()
                if not token:
                    raise RuntimeError("EDDY_INTELLIGENCE_TOKEN ausente")
                headers["Authorization"] = "Bearer " + token
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=2) as response:
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

# Worker separado da UI: monitoramento não depende de sessões Streamlit.
if [[ "${EDDY_DB_ENGINE:-sqlite}" == "mysql" && "${EDDY_MYSQL_SYNC_ENABLED:-true}" == "true" ]]; then
  echo "[EDDY] Sincronização Redmine -> MySQL ativa; ações externas exclusivas do executor VR01."
  python -m scripts.sync_eddy_mysql --loop --intervalo "${EDDY_MYSQL_SYNC_INTERVAL_SECONDS:-1800}" &
  pids+=("$!")
fi

# Dedicated, low-frequency Blueprint enrichment; not coupled to VR01 cycles.
if [[ "${EDDY_DB_ENGINE:-sqlite}" == "mysql" && "${EDDY_IDENTITY_REFRESH_ENABLED:-true}" == "true" ]]; then
  echo "[EDDY] Identidade global: MySQL-first; enriquecimento BP diario independente."
  python -m scripts.eddy_identity_mysql_refresh &
  pids+=("$!")
fi

# VR01 MySQL scheduler: internal transitions and external operations are
# governed by per-issue preflight, reconciliation and readiness checks.
if [[ "${EDDY_DB_ENGINE:-sqlite}" == "mysql" && "${EDDY_VR01_OBSERVER_ENABLED:-true}" == "true" ]]; then
  echo "[EDDY] VR01 MySQL scheduler iniciado; offline_first=${EDDY_VR01_OFFLINE_FIRST}; portfolio=${EDDY_VR01_PORTFOLIO_ENABLED}; external=${EDDY_VR01_EXTERNAL_ENABLED}."
  python -m scripts.eddy_vr01_mysql_scheduler &
  pids+=("$!")
fi

if [[ "${EDNNA_MONITOR_EMAIL_ENABLED:-false}" == "true" ]]; then
  echo "[EDDY] Worker operacional habilitado explicitamente."
  python -m ednna.worker_operacional &
  pids+=("$!")
else
  echo "[EDDY] Worker operacional desabilitado; configurar EDNNA_MONITOR_EMAIL_ENABLED=true após homologação."
fi

if [[ "${EDDY_MOTORES_OBSERVABILIDADE_ENABLED:-true}" == "true" ]]; then
  python -m ednna.observabilidade_motores &
  pids+=("$!")
fi

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
