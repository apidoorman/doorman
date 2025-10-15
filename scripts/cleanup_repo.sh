#!/usr/bin/env bash
set -euo pipefail

echo "[cleanup] Removing caches and runtime artifacts..."
find . -type d -name "__pycache__" -prune -exec rm -rf {} + || true
find . -type d -name ".pytest_cache" -prune -exec rm -rf {} + || true
find . -type f -name "*.py[co]" -delete || true
find . -type f -name ".DS_Store" -delete || true
rm -rf backend-services/platform-logs/*.log backend-services/doorman.pid doorman.pid uvicorn.pid || true
rm -rf web-client/.next || true
rm -f pytest_backend_verbose.log || true

if [[ "${1-}" == "--deep" ]]; then
  echo "[cleanup] Removing generated dev artifacts..."
  rm -rf generated backend-services/generated || true
fi

echo "[cleanup] Done."

