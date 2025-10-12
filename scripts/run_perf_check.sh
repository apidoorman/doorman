#!/usr/bin/env bash
set -euo pipefail

# Runs k6 load-tests/k6-load-test.js, captures CPU/loop-lag stats while running,
# and compares results against a baseline summary via scripts/compare_perf.py.

BASE_URL=${BASE_URL:-http://localhost:8000}
BASELINE_JSON=${BASELINE_JSON:-load-tests/baseline/k6-summary.json}
CURRENT_JSON=${CURRENT_JSON:-load-tests/k6-summary.json}
PERF_JSON=${PERF_JSON:-load-tests/perf-stats.json}

echo "Using BASE_URL=${BASE_URL}"
echo "Baseline file: ${BASELINE_JSON}"

if ! command -v k6 >/dev/null 2>&1; then
  echo "Error: k6 is not installed. Install from https://k6.io/docs/get-started/installation/" >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found" >&2
  exit 2
fi

# Launch perf capture in background (optional; will fall back gracefully if pidfile is missing)
python3 scripts/capture_perf_stats.py --output "${PERF_JSON}" --pidfile backend-services/doorman.pid --timeout 0 \
  >/dev/null 2>&1 &
MONITOR_PID=$!

cleanup() {
  if kill -0 "${MONITOR_PID}" >/dev/null 2>&1; then
    kill "${MONITOR_PID}" >/dev/null 2>&1 || true
    wait "${MONITOR_PID}" || true
  fi
}
trap cleanup EXIT INT TERM

echo "Running k6 load test..."
K6_CMD=(k6 run load-tests/k6-load-test.js --env BASE_URL="${BASE_URL}")
"${K6_CMD[@]}"

echo
echo "k6 summary written to: ${CURRENT_JSON}"

if [ ! -f "${BASELINE_JSON}" ]; then
  echo "Baseline summary not found at ${BASELINE_JSON}" >&2
  echo "Create one by copying a known-good run, e.g.:" >&2
  echo "  mkdir -p \"$(dirname \"${BASELINE_JSON}\")\" && cp '${CURRENT_JSON}' '${BASELINE_JSON}'" >&2
  exit 3
fi

echo
echo "Comparing current vs baseline..."
python3 scripts/compare_perf.py "${CURRENT_JSON}" "${BASELINE_JSON}"

