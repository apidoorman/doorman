# Operations Guide (Doorman Gateway)

This document summarizes production configuration, deployment runbooks, and key operational endpoints for Doorman.

## Environment Configuration

Recommended production defaults (see `.env`):

- HTTPS_ONLY=true — set `Secure` flag on cookies
- HTTPS_ENABLED=true — enforce CSRF double-submit for cookie auth
- CORS_STRICT=true — disallow wildcard origins; whitelist your domains via `ALLOWED_ORIGINS`
- LOG_FORMAT=json — optional JSON log output for production log pipelines
- MAX_BODY_SIZE_BYTES=1048576 — reject requests with Content-Length above 1 MB
- STRICT_RESPONSE_ENVELOPE=true — platform APIs return consistent envelopes

Unified cache/DB flags:

- MEM_OR_EXTERNAL=MEM|REDIS — unified flag for cache/DB mode
- MEM_OR_REDIS — deprecated alias still accepted for backward compatibility

JWT/Token encryption:

- JWT_SECRET_KEY — REQUIRED; gateway fails fast if missing at startup
- TOKEN_ENCRYPTION_KEY — recommended; encrypts stored API keys and user API keys at rest

Core variables:

- ALLOWED_ORIGINS — comma-separated list of allowed origins
- ALLOW_CREDENTIALS — set to true only with explicit origins
- ALLOW_METHODS, ALLOW_HEADERS — scope to what you need
- JWT_SECRET_KEY — rotate periodically; store in a secret manager
- MEM_OR_REDIS — MEM or REDIS depending on cache backing
- MONGO_DB_HOSTS, MONGO_REPLICA_SET_NAME — enable DB in non-memory mode

## Security

- Cookies: access_token_cookie is HttpOnly; set Secure via HTTPS_ONLY. CSRF cookie (`csrf_token`) issued on login/refresh.
- CSRF: when HTTPS_ENABLED=true, clients must include `X-CSRF-Token` header matching `csrf_token` cookie on protected endpoints.
- CORS: avoid wildcard with credentials; use explicit allowlists.
- Logging: includes redaction filter to reduce token/password leakage. Avoid logging PII.
- Rate limiting: Redis-based limiter; if Redis is unavailable the gateway falls back to a process-local in-memory limiter (non-distributed). Configure user limits in DB/role as needed.
- Request limits: global Content-Length check; per-route multipart (proto upload) size limits via MAX_MULTIPART_SIZE_BYTES.
- Response envelopes: `STRICT_RESPONSE_ENVELOPE=true` makes platform API responses consistent for client parsing.

## Health and Monitoring

- Liveness: `GET /platform/monitor/liveness` → `{ status: "alive" }`
- Readiness: `GET /platform/monitor/readiness` → `{ status, mongodb, redis }`
- Metrics: `GET /platform/monitor/metrics?range=24h` (auth required; manage_gateway)
- Logging: `/platform/logging/*` endpoints; requires `view_logs`/`export_logs`

## Deployment

1. Configure `.env` with production values (see above) or environment variables.
2. Run behind an HTTPS-capable reverse proxy (or enable HTTPS in-process with `HTTPS_ONLY=true` and valid certs).
3. Set ALLOWED_ORIGINS to your web client domains; set ALLOW_CREDENTIALS=true only when needed.
4. Provision Redis (recommended) and MongoDB (optional in memory-only mode). In memory mode, enable encryption key for dumps and consider TOKEN_ENCRYPTION_KEY for API keys.
5. Rotate JWT_SECRET_KEY periodically; plan for key rotation and token invalidation.
6. Memory-only mode requires a single worker (THREADS=1); multiple workers will have divergent in-memory state.

## Runbooks

- Restarting gateway:
  - Graceful stop writes a final encrypted memory dump in memory-only mode.
- Token leakage suspect:
  - Invalidate tokens (`/platform/authorization/invalidate`), rotate JWT secret if necessary, audit logs (redaction is best-effort).
- Elevated error rates:
  - Check readiness endpoint; verify Redis/Mongo health; inspect logs via `/platform/logging/logs`.
- CORS failures:
  - Verify ALLOWED_ORIGINS and CORS_STRICT settings; avoid `*` with credentials.
  - Use Tools → CORS Checker (or POST `/platform/tools/cors/check`) to simulate preflight/actual decisions and view effective headers.
- CSRF errors:
  - Ensure clients set `X-CSRF-Token` header to value of `csrf_token` cookie when HTTPS_ENABLED=true.

## Notes

- Gateway (proxy) responses can be optionally wrapped by STRICT_RESPONSE_ENVELOPE; confirm client contracts before enabling globally in front of external consumers.
- Prefer Authorization: Bearer header for external API consumers to reduce CSRF surface.

## Strict Envelope Examples

When `STRICT_RESPONSE_ENVELOPE=true`, platform endpoints return a consistent structure.

- Success (200):
```
{
  "status_code": 200,
  "response": { "key": "value" }
}
```

- Created (201):
```
{
  "status_code": 201,
  "message": "Resource created successfully"
}
```

- Error (400/403/404):
```
{
  "status_code": 403,
  "error_code": "ROLE009",
  "error_message": "You do not have permission to create roles"
}
```
