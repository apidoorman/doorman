# Troubleshooting

Quick checks and tools to resolve common issues.

## Authorization fails (401/403)

- Verify cookies: `access_token_cookie` and `csrf_token` exist.
- In HTTPS mode, X‑CSRF‑Token header must match `csrf_token` cookie.
- Ensure user is active and has `ui_access` for console.

## 429 Too Many Requests

- Check user Rate/Throttle settings; raise or disable for tests.
- Use `DELETE /api/caches` between load tests to reset counters.

## CORS errors

- Use CORS Checker (Tools) with your origin/method/headers.
- Avoid wildcard `*` with credentials.

## Upstream errors (5xx)

- Check upstream availability and timeouts in API config.
- Review Logs and Monitor → Metrics for error spikes.

## Cache clear

`DELETE /api/caches` (requires permission) clears gateway caches and rate counters.

