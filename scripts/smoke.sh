#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5001}"
EMAIL="${DOORMAN_ADMIN_EMAIL:-}"
PASSWORD="${DOORMAN_ADMIN_PASSWORD:-}"

if [[ -z "$EMAIL" ]]; then
  echo "ERROR: DOORMAN_ADMIN_EMAIL must be set" >&2
  exit 1
fi

if [[ -z "$PASSWORD" ]]; then
  echo "ERROR: DOORMAN_ADMIN_PASSWORD must be set" >&2
  exit 1
fi

echo "[1/4] Checking liveness..."
curl -sfS "$BASE_URL/platform/monitor/liveness" | grep -q '"alive"' && echo "OK" || { echo "Liveness failed"; exit 1; }

echo "[2/4] Checking readiness..."
curl -sfS "$BASE_URL/platform/monitor/readiness" | grep -q '"ready"' && echo "OK" || { echo "Readiness degraded"; exit 1; }

echo "[3/4] Logging in..."
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT
curl -sfS -c "$COOKIE_JAR" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  "$BASE_URL/platform/authorization" > /dev/null && echo "OK" || { echo "Login failed"; exit 1; }

echo "[4/4] Verifying token status..."
curl -sfS -b "$COOKIE_JAR" "$BASE_URL/platform/authorization/status" | grep -q '"Token is valid"' && echo "OK" || { echo "Token status check failed"; exit 1; }

echo "Smoke checks passed."

