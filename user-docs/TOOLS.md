# Tools and Diagnostics

This page describes built-in tools available to help operate and troubleshoot your Doorman gateway.

## CORS Checker

Validate your CORS configuration without trial-and-error in a browser.

- UI: Navigate to `/tools` in the web client (requires `manage_security` permission).
- API: `POST /platform/tools/cors/check` (requires `manage_security`).

Request body:
```
{
  "origin": "https://app.example.com",
  "method": "GET",
  "request_headers": ["Content-Type", "Authorization"],
  "with_credentials": true
}
```

Response highlights:
- `config`: Effective CORS configuration derived from environment variables.
- `preflight`: Whether the preflight would be allowed and the headers that would be returned.
- `actual`: Whether an actual request would be allowed and expected response headers.
- `notes`: Guidance for common misconfigurations (e.g., wildcard with credentials).

Environment variables considered:
- `ALLOWED_ORIGINS`, `ALLOW_METHODS`, `ALLOW_HEADERS`, `ALLOW_CREDENTIALS`, `CORS_STRICT`.

Tips:
- Avoid `*` origins when `ALLOW_CREDENTIALS=true`; explicitly list origins or enable `CORS_STRICT=true`.
- If `ALLOW_HEADERS='*'` is set with credentials, the gateway applies a conservative default set.

