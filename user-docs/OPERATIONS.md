Doorman Operations Runbooks
===========================

Overview
--------
Operational playbooks for common gateway actions with exact commands and example responses. Unless noted, endpoints require an authenticated admin session (manage_gateway or manage_auth permissions as applicable).

Authentication (Admin Session)
------------------------------
- Set a base URL and use a cookie jar for convenience:
  - `export BASE=http://localhost:3001`
  - `export COOKIE=/tmp/doorman.ops.cookies`
- Obtain a JWT session cookie via platform login:
  - Command:
    - curl -i -c "$COOKIE" -X POST \
      -H 'Content-Type: application/json' \
      -d '{"email":"admin@doorman.dev","password":"<ADMIN_PASSWORD>"}' \
      "$BASE/platform/authorization"
  - Look for a `Set-Cookie: access_token_cookie=...;` header. Use this cookie in subsequent commands.

Cache Flush
-----------
- Purpose: Clear all in-memory/redis caches (users, roles, APIs, routing, etc.) and reset rate/throttle counters.
- Endpoint: DELETE `$BASE/api/caches`
- Requirements: Admin user with `manage_gateway` access; authenticated session.
- Command:
  - curl -i -b "$COOKIE" -X DELETE \
    -H 'Content-Type: application/json' \
    "$BASE/api/caches"
- Expected response:
  - Status: 200 OK
  - Body: {"message":"All caches cleared"}

Revoke-All Tokens (Per User)
----------------------------
- Purpose: Immediately revoke all active tokens for a specific user across workers/nodes (uses durable storage when configured).
- Endpoints:
  - Revoke: POST `$BASE/platform/authorization/admin/revoke/{username}`
  - Unrevoke: POST `$BASE/platform/authorization/admin/unrevoke/{username}`
- Requirements: Admin with `manage_auth` access; authenticated session.
- Revoke command:
  - curl -i -b "$COOKIE" -X POST \
    -H 'Content-Type: application/json' \
    "$BASE/platform/authorization/admin/revoke/alice"
- Expected revoke response:
  - Status: 200 OK
  - Body: {"message":"All tokens revoked for alice"}
- Unrevoke command:
  - curl -i -b "$COOKIE" -X POST \
    -H 'Content-Type: application/json' \
    "$BASE/platform/authorization/admin/unrevoke/alice"
- Expected unrevoke response:
  - Status: 200 OK
  - Body: {"message":"Token revocation cleared for alice"}

Hot Reload (SIGHUP)
-------------------
- Purpose: Reload hot-reloadable configuration without restarting the process.
- Signal-based reload:
  - Prereq: Doorman is running and the Rust gateway PID is available when process metrics are required.
  - Command:
    - kill -HUP $(cat doorman.pid)
  - Expected outcome:
    - Process stays up; logs include "SIGHUP received: reloading configuration..." and "Configuration reload complete".
    - Log level updates if `LOG_LEVEL` changed; other reloadable keys apply immediately.
- HTTP-triggered reload (alternative to SIGHUP):
  - Endpoint: POST `$BASE/platform/config/reload`
  - Command:
    - curl -i -b "$COOKIE" -X POST \
      -H 'Content-Type: application/json' \
      "$BASE/platform/config/reload"
  - Expected response:
    - Status: 200 OK
    - Headers: may include `X-Request-ID`
    - Body contains `{ "data": { "message": "Configuration reloaded successfully", "config": { ... }}}`
- Inspect current config and reload hints:
  - Endpoint: GET `$BASE/platform/config/current`
  - Command:
    - curl -i -b "$COOKIE" \
      "$BASE/platform/config/current"
  - Expected response:
    - Status: 200 OK
    - Body includes `data.config` and `reload_command: "kill -HUP $(cat doorman.pid)"`

Notes
-----
- Request IDs: Many admin endpoints include an `X-Request-ID` response header for traceability; some utility endpoints (e.g., cache flush) may omit it.
- Permissions: Cache flush requires `manage_gateway`. Revoke endpoints require `manage_auth`. Config routes require `manage_gateway`.
- Cookies: Browser and curl examples rely on `access_token_cookie`; alternatively, platform APIs may return an `access_token` field usable in Authorization headers where supported.

Release Candidate Runbook
-------------------------
- Scope: Run this against the exact immutable image digest proposed for release,
  a production-like MongoDB replica set, and a separate Redis instance. Keep
  the generated artifacts under `release-evidence/` and do not overwrite a
  prior candidate's directory.
- Image smoke:
  - Start the candidate with the production environment, then run:
    - `BASE_URL=https://candidate.example.com DOORMAN_ADMIN_EMAIL=<admin> DOORMAN_ADMIN_PASSWORD=<password> bash scripts/smoke.sh`
  - Record the image digest, UTC timestamp, target URL, and a successful result
    in `release-evidence/operations.json` under `image_smoke`.
- Restore rehearsal:
  - Restore a scrubbed MongoDB backup into an isolated candidate database and
    restore the matching Redis snapshot/keyspace. Start a fresh candidate,
    run the smoke command above, and verify a known API, endpoint, role, and
    subscription are present.
  - Record the backup identifier and successful result under `restore_rehearsal`.
- Canary:
  - Send a small, observable portion of traffic to the candidate. Keep the
    canary long enough to cover authentication, REST, GraphQL, SOAP, and gRPC
    requests plus background policy writes. Watch readiness, error rate,
    p95 latency, upstream timeouts, and retry rate against the existing
    deployment's baseline.
  - Abort the canary on any security error, a sustained 5xx increase, or an
    SLO breach; record the traffic percentage, duration, dashboard links, and
    successful result under `canary`.
- Rollback:
  - Revert traffic to the prior immutable image, verify readiness and the
    smoke command, then prove the restored configuration remains available.
    Do not delete candidate databases or evidence until incident review is
    complete.
  - Record the prior digest, UTC timestamp, smoke result, and successful
    result under `rollback`.
- Final evidence:
  - Write a schema-version-1 `release-evidence/operations.json` such as:
    - `{"schema_version":1,"image_smoke":{"passed":true},"restore_rehearsal":{"passed":true},"canary":{"passed":true},"rollback":{"passed":true}}`
  - Run `make release-check` with all report variables from `user-docs/TESTS.md`.
    It fails closed if any operational rehearsal is absent, failed, or stale.
