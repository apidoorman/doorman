#!/usr/bin/env bash
set -euo pipefail

# Run the demo compose stack and auto-clean containers, networks, and volumes on exit.

COMPOSE=${COMPOSE:-docker compose}
FILES="-f docker-compose.yml -f docker-compose.demo.yml"
PROJECT=${PROJECT:-doorman-demo-$(date +%s)}

cleanup() {
  echo "[demo] Cleaning up demo stack..."
  $COMPOSE $FILES -p "$PROJECT" down -v --remove-orphans || true
}

trap cleanup EXIT INT TERM

echo "[demo] Starting demo stack (project: $PROJECT)..."
$COMPOSE $FILES -p "$PROJECT" up --abort-on-container-exit --force-recreate
