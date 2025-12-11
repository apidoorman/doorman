#!/usr/bin/env bash
set -euo pipefail

# Load environment variables from common .env files if they exist.
# Order: /env/*.env -> repo root .env -> backend-services/.env -> web-client/.env -> production variants
_apply_env_file_no_override() {
  # Read KEY=VALUE lines and export only if KEY is not already set in the environment.
  # Supports simple quoted values. Skips comments and blank lines.
  local file="$1"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|'#'*) continue ;;
    esac
    # Strip export if present
    line=${line#export }
    # Only simple KEY=VALUE pairs
    if printf '%s' "$line" | grep -Eq '^[A-Za-z_][A-Za-z0-9_]*='; then
      key="${line%%=*}"
      val="${line#*=}"
      # Trim surrounding quotes
      if [ "${val#\"}" != "$val" ] && [ "${val%\"}" != "$val" ]; then
        val="${val#\"}"; val="${val%\"}"
      elif [ "${val#\'}" != "$val" ] && [ "${val%\'}" != "$val" ]; then
        val="${val#\'}"; val="${val%\'}"
      fi
      # Only set if not already defined
      if [ -z "${!key+x}" ]; then
        export "$key"="$val"
      fi
    fi
  done < "$file"
}

load_env_files() {
  # Load env files without overriding already-set variables.
  # Precedence: platform/injected env > /env files > repo .env files (backend/web/app)
  set +u
  for dir in /env /app/backend-services /app/web-client /app; do
    if [ -d "$dir" ]; then
      for f in "$dir"/.env* "$dir"/*.env; do
        # Skip non-existent and example templates
        if [ -f "$f" ] && ! printf '%s' "$f" | grep -qE '\.example$'; then
          echo "[entrypoint] Loading env file: $f"
          _apply_env_file_no_override "$f"
        fi
      done
    fi
  done
  set -u
}

graceful_stop() {
  echo "[entrypoint] Stopping services..."
  # Stop backend
  if [ -d /app/backend-services ]; then
    ( cd /app/backend-services && python doorman.py stop ) || true
  fi
  # Stop web client
  if [ -n "${WEB_PID:-}" ]; then
    kill -TERM "$WEB_PID" 2>/dev/null || true
    wait "$WEB_PID" 2>/dev/null || true
  fi
  exit 0
}

load_env_files

trap graceful_stop SIGTERM SIGINT

# Start backend (Doorman) in the foreground so logs go to container stdout
echo "[entrypoint] Starting Doorman backend..."
(
  cd /app/backend-services
  # Ensure required directories
  mkdir -p proto generated logs
  python doorman.py run
) &
BACK_PID=$!

# Start web client (Next.js)
echo "[entrypoint] Starting web client..."
(
  cd /app/web-client
  # Start Next.js on WEB_PORT, bind to 0.0.0.0 for container networking
  PORT="${WEB_PORT:-3000}" npm run start -- -H 0.0.0.0 -p "${WEB_PORT:-3000}"
) &
WEB_PID=$!

echo "[entrypoint] Services launched. Backend PID=$BACK_PID Web PID=$WEB_PID"

# Wait on either process to exit, then stop gracefully
wait -n || true
graceful_stop
