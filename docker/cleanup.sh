#!/usr/bin/env sh
set -eu

# Best-effort cleanup of demo resources when the stack is stopped via Ctrl+C.
# Requires access to the Docker socket (provided by compose volume mount).

PROJECT="${PROJECT:-doorman-demo}"

echo "[cleanup] Waiting for containers to stop..."
sleep 2

echo "[cleanup] Removing stopped containers for project: $PROJECT"
docker container prune -f --filter "label=com.docker.compose.project=${PROJECT}" || true

echo "[cleanup] Removing volumes for project: $PROJECT"
VOL_IDS=$(docker volume ls -q --filter "label=com.docker.compose.project=${PROJECT}" || true)
if [ -n "${VOL_IDS:-}" ]; then
  echo "$VOL_IDS" | xargs -r docker volume rm -f || true
fi

echo "[cleanup] Removing networks for project: $PROJECT"
NET_IDS=$(docker network ls -q --filter "label=com.docker.compose.project=${PROJECT}" || true)
if [ -n "${NET_IDS:-}" ]; then
  echo "$NET_IDS" | xargs -r docker network rm || true
fi

echo "[cleanup] Done"

