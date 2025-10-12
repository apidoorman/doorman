Doorman Operations Runbooks
===========================

Overview
--------
Operational playbooks for common gateway actions with exact commands and example responses. Unless noted, endpoints require an authenticated admin session (manage_gateway or manage_auth permissions as applicable).

Authentication (Admin Session)
------------------------------
- Obtain a JWT session cookie via platform login:
  - Command:
    - curl -i -X POST \
      -H 'Content-Type: application/json' \
      -d '{"email":"admin@doorman.dev","password":"<ADMIN_PASSWORD>"}' \
      http://localhost:8000/platform/authorization
  - Look for a `Set-Cookie: access_token_cookie=...;` header. Use this cookie in subsequent commands.

Cache Flush
-----------
- Purpose: Clear all in-memory/redis caches (users, roles, APIs, routing, etc.) and reset rate/throttle counters.
- Endpoint: DELETE `http://localhost:8000/api/caches`
- Requirements: Admin user with `manage_gateway` access; authenticated cookie `access_token_cookie`.
- Command:
  - curl -i -X DELETE \
    -H 'Content-Type: application/json' \
    --cookie 'access_token_cookie=<JWT>' \
    http://localhost:8000/api/caches
- Expected response:
  - Status: 200 OK
  - Headers: `X-Request-ID` may be absent for this endpoint
  - Body:
    - {"message":"All caches cleared"}

Revoke-All Tokens (Per User)
----------------------------
- Purpose: Immediately revoke all active tokens for a specific user across workers/nodes (uses durable storage when configured).
- Endpoints:
  - Revoke: POST `http://localhost:8000/platform/authorization/admin/revoke/{username}`
  - Unrevoke: POST `http://localhost:8000/platform/authorization/admin/unrevoke/{username}`
- Requirements: Admin with `manage_auth` access; authenticated cookie `access_token_cookie`.
- Revoke command:
  - curl -i -X POST \
    -H 'Content-Type: application/json' \
    --cookie 'access_token_cookie=<JWT>' \
    http://localhost:8000/platform/authorization/admin/revoke/alice
- Expected revoke response:
  - Status: 200 OK
  - Headers: includes `X-Request-ID: <uuid>`
  - Body:
    - {"message":"All tokens revoked for alice"}
- Unrevoke command:
  - curl -i -X POST \
    -H 'Content-Type: application/json' \
    --cookie 'access_token_cookie=<JWT>' \
    http://localhost:8000/platform/authorization/admin/unrevoke/alice
- Expected unrevoke response:
  - Status: 200 OK
  - Headers: includes `X-Request-ID: <uuid>`
  - Body:
    - {"message":"Token revocation cleared for alice"}

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
  - Endpoint: POST `http://localhost:8000/platform/config/reload`
  - Command:
    - curl -i -X POST \
      -H 'Content-Type: application/json' \
      --cookie 'access_token_cookie=<JWT>' \
      http://localhost:8000/platform/config/reload
  - Expected response:
    - Status: 200 OK
    - Headers: may include `X-Request-ID`
    - Body contains `{ "data": { "message": "Configuration reloaded successfully", "config": { ... }}}`
- Inspect current config and reload hints:
  - Endpoint: GET `http://localhost:8000/platform/config/current`
  - Command:
    - curl -i \
      --cookie 'access_token_cookie=<JWT>' \
      http://localhost:8000/platform/config/current
  - Expected response:
    - Status: 200 OK
    - Body includes `data.config` and `reload_command: "kill -HUP $(cat doorman.pid)"`

Notes
-----
- Request IDs: Many admin endpoints include an `X-Request-ID` response header for traceability; some utility endpoints (e.g., cache flush) may omit it.
- Permissions: Cache flush requires `manage_gateway`. Revoke endpoints require `manage_auth`. Config routes require `manage_gateway`.
- Cookies: Browser and curl examples rely on `access_token_cookie`; alternatively, platform APIs may return an `access_token` field usable in Authorization headers where supported.

