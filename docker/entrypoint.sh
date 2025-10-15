#!/usr/bin/env bash
set -euo pipefail

# Load environment variables from common .env files if they exist.
# Order: /env/*.env -> repo root .env -> backend-services/.env -> web-client/.env -> production variants
load_env_files() {
  # Load any *.env* style files found in common locations. Later files override earlier ones.
  # Examples supported out-of-the-box: .env, .env.production, production.env, .env.local, etc.
  set +u
  set -a
  for dir in /env /app /app/backend-services /app/web-client; do
    if [ -d "$dir" ]; then
      for f in "$dir"/.env* "$dir"/*.env; do
        if [ -f "$f" ]; then
          echo "[entrypoint] Loading env file: $f"
          # shellcheck disable=SC1090
          . "$f"
        fi
      done
    fi
  done
  set +a
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

# Start backend (Doorman)
echo "[entrypoint] Starting Doorman backend..."
(
  cd /app/backend-services
  # Ensure required directories
  mkdir -p proto generated logs
  python doorman.py start
) &
BACK_PID=$!

# Start web client (Next.js)
echo "[entrypoint] Starting web client..."
(
  cd /app/web-client
  # Next.js start on port 3000 by default; override via env if needed.
  npm run start
) &
WEB_PID=$!

echo "[entrypoint] Services launched. Backend PID=$BACK_PID Web PID=$WEB_PID"

# Wait on either process to exit, then stop gracefully
wait -n || true
graceful_stop
