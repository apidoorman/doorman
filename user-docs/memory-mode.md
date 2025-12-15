Memory-Mode (MEM) Dumps: Localhost and AWS Docker

Overview

- Memory-mode keeps state in-process (Mongo memory-only). This doc shows how to persist and restore that state via encrypted memory dumps on localhost and on AWS with Docker/ECS.

What’s implemented

- Auto-dump on graceful shutdown, plus signal handlers for SIGTERM/SIGINT/SIGUSR1.
- Encrypted dumps written to `MEM_DUMP_PATH` (default: `backend-services/generated/memory_dump.bin`).
- Optional autosave with `MEM_AUTO_SAVE_ENABLED` and `MEM_AUTO_SAVE_FREQ` (seconds).
- Startup auto-restore from the latest dump in the target directory.

Requirements

- `MEM_OR_EXTERNAL=MEM` and `THREADS=1` (single worker for memory mode).
- `MEM_ENCRYPTION_KEY` set to a strong secret (>= 8 chars).
- The directory for `MEM_DUMP_PATH` must be writable and persisted (bind mount or volume).

Localhost (docker compose)

- docker-compose.yml already mounts `./generated:/app/backend-services/generated` so dumps persist to your working tree.
- Configure environment in `.env` (recommended):

  - `MEM_ENCRYPTION_KEY=some-strong-secret`
  - Optional: `MEM_AUTO_SAVE_ENABLED=true`
  - Optional: `MEM_AUTO_SAVE_FREQ=300`  # seconds

- Or override via shell when running `docker compose up`.

AWS ECS (task definition outline)

- Persist dumps to a mounted volume (EFS or EBS). Example container config:

  - Mount EFS to `/app/backend-services/generated` (same path used in compose)
  - Set env vars:
    - `MEM_OR_EXTERNAL=MEM`
    - `THREADS=1`
    - `MEM_ENCRYPTION_KEY=your-strong-key`
    - `MEM_DUMP_PATH=/app/backend-services/generated/memory_dump.bin`
    - `MEM_AUTO_SAVE_ENABLED=true`
    - `MEM_AUTO_SAVE_FREQ=300`

- Ensure your service sends `SIGTERM` on scale-in/stop and allows a short drain period so the dump completes.

Signals / Manual dump

- SIGTERM / SIGINT: triggers a dump and then shutdown.
- SIGUSR1: triggers an on-demand dump without terminating.
- HTTP route (requires auth): `POST /platform/memory/dump` accepts optional `{ "path": "<dir or file>" }`.

Verification tips

- After changes (onboard user/API), send SIGUSR1 and check a new `*.bin` in the dump directory.
- Restart the service; logs will report "restored from dump <path>" if a dump exists.

Notes

- Dumps are encrypted (AES-GCM with derived key) using `MEM_ENCRYPTION_KEY`.
- In multi-worker or HA, use Redis-backed persistence and external databases (MEM mode is single-worker only).

