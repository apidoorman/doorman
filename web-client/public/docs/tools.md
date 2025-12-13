# Tools & Diagnostics

Built-in tools for troubleshooting and diagnostics.

## CORS Checker

Simulate preflight/actual decisions for a given origin/method/headers.

UI: Tools → CORS Checker (requires `manage_security`).

API: `POST /platform/tools/cors/check`

```json
{
  "origin": "https://app.example.com",
  "method": "POST",
  "request_headers": ["Content-Type", "Authorization"],
  "with_credentials": true
}
```

## Readiness / Metrics

- `GET /platform/monitor/liveness` – basic liveness (public)
- `GET /platform/monitor/readiness` – readiness; detailed info with permission
- `GET /platform/monitor/metrics` – usage/latency/bandwidth (requires `manage_gateway`)

## Cache & Admin Utilities

- `DELETE /api/caches` – clear gateway caches
- `POST /platform/security/restart` – schedule safe restart

