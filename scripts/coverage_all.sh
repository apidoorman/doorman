#!/usr/bin/env bash
set -euo pipefail

# End-to-end coverage:
# - Runs the backend under coverage (parallel mode)
# - Executes live-tests against it
# - Combines .coverage files and prints a report
#
# Env:
#   BASE_URL (default http://localhost:5001)
#   DOORMAN_ADMIN_EMAIL, DOORMAN_ADMIN_PASSWORD (required for live tests)

BASE_URL="${BASE_URL:-http://localhost:5001}"
EMAIL="${DOORMAN_ADMIN_EMAIL:-}"
PASSWORD="${DOORMAN_ADMIN_PASSWORD:-}"

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "[coverage] ERROR: DOORMAN_ADMIN_EMAIL and DOORMAN_ADMIN_PASSWORD must be set" >&2
  exit 1
fi

PORT="${PORT:-5001}"

pushd backend-services >/dev/null

echo "[coverage] Starting server under coverage on port $PORT..."
ENV=development PORT=$PORT \
  coverage run --parallel-mode -m uvicorn doorman:doorman &
PID=$!
trap 'kill -9 $PID >/dev/null 2>&1 || true' EXIT

echo "[coverage] Waiting for readiness..."
deadline=$(( $(date +%s) + 30 ))
while true; do
  if curl -fsS "$BASE_URL/platform/monitor/liveness" >/dev/null 2>&1; then
    break
  fi
  if [[ $(date +%s) -gt $deadline ]]; then
    echo "[coverage] Server did not become ready in time" >&2
    exit 1
  fi
  sleep 1
done

echo "[coverage] Running live tests..."
pushd live-tests >/dev/null
DOORMAN_BASE_URL="$BASE_URL" \
DOORMAN_ADMIN_EMAIL="$EMAIL" \
DOORMAN_ADMIN_PASSWORD="$PASSWORD" \
pytest -q || { echo "[coverage] Live tests failed" >&2; exit 1; }
popd >/dev/null

echo "[coverage] Stopping server..."
kill $PID || true
sleep 1

echo "[coverage] Combining and reporting..."
coverage combine || true
coverage report -m || true
echo "[coverage] Done"

popd >/dev/null

