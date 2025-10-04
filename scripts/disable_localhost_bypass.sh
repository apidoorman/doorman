#!/usr/bin/env bash
set -euo pipefail

# One-time helper to force-clear stored allow_localhost_bypass=false via REST API.
# Env vars:
# - BASE_URL (default http://localhost:5001)
# - STARTUP_ADMIN_EMAIL (default admin@localhost)
# - STARTUP_ADMIN_PASSWORD (default password1)

BASE_URL="${BASE_URL:-http://localhost:5001}"
EMAIL="${STARTUP_ADMIN_EMAIL:-admin@localhost}"
PASSWORD="${STARTUP_ADMIN_PASSWORD:-password1}"

echo "[1/3] Logging in to $BASE_URL ..."
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT
curl -sfS -c "$COOKIE_JAR" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  "$BASE_URL/platform/authorization" > /dev/null

echo "[2/3] Forcing allow_localhost_bypass=false ..."
curl -sfS -b "$COOKIE_JAR" -H 'Content-Type: application/json' -X PUT \
  -d '{"allow_localhost_bypass": false}' \
  "$BASE_URL/platform/security/settings" > /dev/null

echo "[3/3] Done. Stored allow_localhost_bypass is now false."

