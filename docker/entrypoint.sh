#!/usr/bin/env bash
set -euo pipefail

_apply_env_file_no_override() {
  local file="$1"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    line=${line#export }
    if printf '%s' "$line" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*='; then
      key="${line%%=*}"
      val="${line#*=}"
      if [ "${val#\"}" != "$val" ] && [ "${val%\"}" != "$val" ]; then
        val="${val#\"}"; val="${val%\"}"
      elif [ "${val#\'}" != "$val" ] && [ "${val%\'}" != "$val" ]; then
        val="${val#\'}"; val="${val%\'}"
      fi
      if [ -z "${!key+x}" ]; then
        export "$key=$val"
      fi
    fi
  done < "$file"
}

load_env_files() {
  set +u
  for dir in /env /app/backend-services /app/web-client /app; do
    if [ -d "$dir" ]; then
      for f in "$dir"/.env* "$dir"/*.env; do
        if [ -f "$f" ] && ! printf '%s' "$f" | grep -qE '\.example$'; then
          echo "[entrypoint] Loading env file: $f"
          _apply_env_file_no_override "$f"
        fi
      done
    fi
  done
  set -u
}

stop_pid() {
  local pid="${1:-}"
  if [ -n "$pid" ]; then
    kill -TERM "$pid" 2>/dev/null || true
  fi
}

graceful_stop() {
  trap - SIGTERM SIGINT
  echo "[entrypoint] Stopping services..."
  stop_pid "${RUST_PID:-}"
  stop_pid "${BACK_PID:-}"
  stop_pid "${WEB_PID:-}"
  wait "${RUST_PID:-}" 2>/dev/null || true
  wait "${BACK_PID:-}" 2>/dev/null || true
  wait "${WEB_PID:-}" 2>/dev/null || true
  exit 0
}

load_env_files

trap graceful_stop SIGTERM SIGINT

PYTHON_INTERNAL_PORT="${PYTHON_INTERNAL_PORT:-3002}"
PYTHON_INTERNAL_URL="${PYTHON_INTERNAL_URL:-http://127.0.0.1:${PYTHON_INTERNAL_PORT}}"
export PYTHON_INTERNAL_PORT PYTHON_INTERNAL_URL DOORMAN_PLATFORM_ONLY=true

# Python mounts only /platform/* and is not published outside this container.
echo "[entrypoint] Starting Python platform service on 127.0.0.1:${PYTHON_INTERNAL_PORT}..."
(
  cd /app/backend-services
  mkdir -p proto generated logs
  exec env HOST=127.0.0.1 PORT="${PYTHON_INTERNAL_PORT}" python doorman.py run
) &
BACK_PID=$!

# Rust owns every public gateway route and proxies only /platform/* to Python.
echo "[entrypoint] Starting Rust gateway on 0.0.0.0:${PORT:-3001}..."
(
  exec env PORT="${PORT:-3001}" PYTHON_INTERNAL_URL="${PYTHON_INTERNAL_URL}" /usr/local/bin/doorman-gateway
) &
RUST_PID=$!

# Next.js remains on the existing public web port.
echo "[entrypoint] Starting web client..."
(
  cd /app/web-client
  exec env PORT="${WEB_PORT:-3000}" npm run start -- -H 0.0.0.0 -p "${WEB_PORT:-3000}"
) &
WEB_PID=$!

echo "[entrypoint] Services launched. Rust PID=$RUST_PID Python PID=$BACK_PID Web PID=$WEB_PID"

if [ "${DEMO_SEED:-false}" = "true" ]; then
  (
    set +e
    BASE="http://localhost:${PORT:-3001}"
    echo "[entrypoint] Waiting for backend to become healthy before seeding..."
    for _ in $(seq 1 40); do
      if curl -sf "${BASE}/platform/monitor/liveness" >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    COOKIE_FILE="/tmp/doorman.demo.cookies"
    if curl -sc "$COOKIE_FILE" -H 'Content-Type: application/json' \
      -d "{\"email\":\"${DOORMAN_ADMIN_EMAIL:-admin@doorman.dev}\",\"password\":\"${DOORMAN_ADMIN_PASSWORD:-change-me}\"}" \
      "${BASE}/platform/authorization" >/dev/null 2>&1; then
      curl -sb "$COOKIE_FILE" -X POST "${BASE}/platform/demo/seed" >/dev/null 2>&1 || true
      echo "[entrypoint] Demo seed triggered"
    else
      echo "[entrypoint] Demo seed skipped (login failed)"
    fi
    rm -f "$COOKIE_FILE" 2>/dev/null || true
  ) &
fi

wait -n "$RUST_PID" "$BACK_PID" "$WEB_PID" || true
graceful_stop
