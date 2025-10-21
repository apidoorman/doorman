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
  - Prereq: Doorman started via `python backend-services/doorman.py start` to create `doorman.pid`.
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
