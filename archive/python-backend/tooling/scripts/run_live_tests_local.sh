#!/usr/bin/env bash
set -euo pipefail

# Run Doorman live tests from host against Docker services on localhost:3001
# - Creates a local venv (./venv if not present)
# - Installs backend test dependencies
# - Sources admin credentials from repo .env (fallbacks preserved by tests)
# - Runs pytest for backend-services/live-tests

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REQ_FILE="$ROOT_DIR/backend-services/requirements.txt"
ENV_FILE="$ROOT_DIR/.env"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required on host" >&2
  exit 1
fi

# Create or reuse venv at ./venv
VENV_DIR="$ROOT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "[live-tests] Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "[live-tests] Installing backend test dependencies from $REQ_FILE"
pip install --upgrade pip >/dev/null
pip install -r "$REQ_FILE"

# Export env if present in .env (tests also read .env directly if not set)
if [ -f "$ENV_FILE" ]; then
  echo "[live-tests] Loading credentials from $ENV_FILE"
  # shellcheck disable=SC2046
  export $(grep -E '^(DOORMAN_ADMIN_EMAIL|DOORMAN_ADMIN_PASSWORD|PORT|HTTPS_ONLY|COOKIE_DOMAIN)=' "$ENV_FILE" | xargs)
fi

# Default base URL to localhost:PORT (port from .env or 3001)
DOORMAN_BASE_URL="${DOORMAN_BASE_URL:-http://localhost:${PORT:-3001}}"
export DOORMAN_BASE_URL

# Ensure servers started by tests are reachable from Dockerized gateway
export DOORMAN_IN_DOCKER=${DOORMAN_IN_DOCKER:-1}

echo "[live-tests] Target: $DOORMAN_BASE_URL"
echo "[live-tests] Running pytest backend-services/live-tests"
cd "$ROOT_DIR"
pytest -q backend-services/live-tests
