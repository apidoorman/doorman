# How‑to: Publish a REST API

Publish upstream REST services through the gateway with access control, CORS, and rate limits.

## Minimum Steps

1. Create API (name/version, upstream servers)
2. Add Endpoints (methods + URIs)
3. Allow roles/groups and subscribe users

### Create API

UI: APIs → Add → fill `api_name`, `api_version`, `api_servers` (e.g., http://httpbin.org)

API example:
```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "api_description": "Customers REST API",
    "api_servers": ["http://httpbin.org"],
    "api_type": "REST",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_allowed_retry_count": 0
  }'
```

### Add Endpoints

```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "endpoint_method": "GET",
    "endpoint_uri": "/get",
    "endpoint_description": "Echo GET"
  }'
```

### Subscribe User

```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "admin",
    "api_name": "customers",
    "api_version": "v1"
  }'
```

### Test

```bash
curl -b $COOKIE "$BASE/api/rest/customers/v1/get?hello=world"
```

## Common Add‑Ons

### CORS (per API)

Set allowed origins/headers/methods in the API’s CORS section. Use the CORS checker if unsure.

### Auth Header Mapping

Inject API keys or map fields to headers (e.g., place bearer token in `Authorization`).

### Rate Limits

Use user rate/throttle settings or tier rules; verify with Monitor → Metrics.

