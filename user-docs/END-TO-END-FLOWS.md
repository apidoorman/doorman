# Doorman (pygate) — End-to-End Flows

This guide walks through common, real-world flows: onboarding a REST API, injecting API keys, client-specific routing, request validation, logging/monitoring, and examples for GraphQL and SOAP.

Throughout, the platform API lives under `/platform/*` and the runtime gateway under `/api/*`.

## Conventions used below
```
BASE=http://localhost:5001        # backend URL
COOKIE=/tmp/doorman.cookies       # cookie jar path
```

Login and check status:
```
curl -s -c "$COOKIE" -H 'Content-Type: application/json' \
  -d '{"email":"admin@localhost","password":"password1"}' \
  "$BASE/platform/authorization"
curl -s -b "$COOKIE" "$BASE/platform/authorization/status"
```

## Flow 1: Publish a REST API with API-key injection and validation

Scenario: You want to publish `/api/rest/customers/v1/*` backed by `http://httpbin:80` for demo/testing, inject `x-api-key` on outbound calls, and validate request payloads.

1) Define a token group (used for outbound API-key injection)
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/token" -d '{
    "api_token_group": "demo-customers",
    "api_key": "demo-secret-123",
    "api_key_header": "x-api-key",
    "token_tiers": [ {"tier_name": "default", "tokens": 999999, "input_limit": 0, "output_limit": 0, "reset_frequency": "monthly"} ]
  }'
```

2) Create the API with restricted headers and token group
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "api_description": "Demo customers API",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["http://httpbin:80"],
    "api_type": "REST",
    "api_allowed_retry_count": 0,
    "api_allowed_headers": ["content-type", "accept"],
    "api_tokens_enabled": true,
    "api_token_group": "demo-customers"
  }'
```

3) Add endpoints you want to expose
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers", "api_version": "v1",
    "endpoint_method": "GET", "endpoint_uri": "/get",
    "endpoint_description": "Echo request"
  }'

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers", "api_version": "v1",
    "endpoint_method": "POST", "endpoint_uri": "/post",
    "endpoint_description": "Echo posted JSON"
  }'
```

4) (Optional) Attach endpoint-level validation (e.g., require `user.name` on POST)
```
# Get the endpoint_id for POST /post (via UI or endpoint listing)
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint/endpoint/validation" -d '{
    "endpoint_id": "<endpoint_id>",
    "validation_enabled": true,
    "validation_schema": {"validation_schema": {"user.name": {"required": true, "type": "string", "min": 2}}}
  }'
```

5) Subscribe a user to the API
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "admin", "api_name": "customers", "api_version": "v1"
  }'
```

6) Call the gateway (Doorman injects `x-api-key` from your token group)
```
curl -s -b "$COOKIE" "$BASE/api/rest/customers/v1/get?demo=1"

curl -s -b "$COOKIE" -H 'Content-Type: application/json' \
  -d '{"user": {"name": "Alice"}}' \
  "$BASE/api/rest/customers/v1/post"
```

Validation failures return HTTP 400 and do not reach the upstream.

## Flow 2: Client-specific routing

Route different clients to different upstream pools using a `client-key` header.

1) Create a routing entry for a client
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/routing" -d '{
    "routing_name": "customers-routing",
    "routing_servers": ["http://upstream-a:8080", "http://upstream-b:8080"],
    "routing_description": "Pool for enterprise client",
    "client_key": "enterprise-A"
  }'
```

2) Call the gateway with header `client-key: enterprise-A`
```
curl -s -b "$COOKIE" -H 'client-key: enterprise-A' \
  "$BASE/api/rest/customers/v1/get"
```

Precedence when picking upstream: Routing (client), then Endpoint-level servers, then API-level servers.

## Flow 3: Per-user tokens for paid/limited APIs

The token system supports deducting per-user credits when calling an API and injecting per-user API keys.

1) Define a token group and tiers (as in Flow 1)
2) Assign a user-specific API key (overrides group key when present)
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/token/{username}" -d '{
    "api_token_group": "demo-customers",
    "api_key": "USER-SPECIFIC-KEY",
    "api_key_header": "x-api-key",
    "token_tiers": [ {"tier_name": "premium", "tokens": 10000, "input_limit": 1000, "output_limit": 1000, "reset_frequency": "monthly"} ]
  }'
```

3) Enable tokens on the API (`api_tokens_enabled=true`, `api_token_group="demo-customers"`). Each gateway call deducts a token; if the user runs out, calls return 401 with `GTW008`.

## Flow 4: GraphQL gateway

Doorman proxies GraphQL at `/api/graphql/{apiName}`. You must send `X-API-Version` and optionally attach validation per-API.

1) Define the API and (optionally) validation
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "countries", "api_version": "v1",
    "api_description": "Public GraphQL",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["https://countries.trevorblades.com"],
    "api_type": "GraphQL",
    "api_allowed_headers": ["content-type"],
    "api_allowed_retry_count": 0
  }'
```

2) Subscribe your user and call the gateway
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' \
  -H 'X-API-Version: v1' \
  -d '{"query":"{ country(code: \"US\"){ name capital } }"}' \
  "$BASE/api/graphql/countries"
```

If validation is enabled on the API, Doorman verifies the GraphQL operation shape and variables before proxying.

## Flow 5: SOAP gateway

SOAP traffic is proxied under `/api/soap/{path}`. You can attach XML-based validation to endpoints.

1) Create API + endpoint for a SOAP operation (example paths)
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "legacy", "api_version": "v1",
    "api_description": "Legacy SOAP",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["http://legacy-soap:8080"],
    "api_type": "SOAP",
    "api_allowed_retry_count": 0,
    "api_allowed_headers": ["content-type"]
  }'

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "legacy", "api_version": "v1",
    "endpoint_method": "POST", "endpoint_uri": "/OrderService/CreateOrder",
    "endpoint_description": "CreateOrder operation"
  }'
```

2) (Optional) Attach XML validation for the SOAP body
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint/endpoint/validation" -d '{
    "endpoint_id": "<endpoint_id>",
    "validation_enabled": true,
    "validation_schema": {"validation_schema": {"orderId": {"required": true, "type": "string"}}}
  }'
```

## Monitoring, Logging, and Health

- Health checks:
  - Liveness: `GET $BASE/platform/monitor/liveness` → `{ "status": "alive" }`
  - Readiness: `GET $BASE/platform/monitor/readiness`
- Gateway status (with Redis/Mongo, memory, uptime): `GET $BASE/api/status`
- Logs: View in the UI under Logging, or tail `backend-services/logs/doorman.log`.
- Metrics: Aggregate per-request metrics are recorded for `/api/*` and surfaced in the dashboard.

## Common Errors and Remedies
- `GTW001` API not found: Check `api_name`/`api_version` and that you created it.
- `GTW002` No endpoints: Add endpoints for the API.
- `GTW003` Endpoint mismatch: Method/URI not in your endpoint set; verify slashes and method.
- `GTW008` No tokens: Enable a token group and ensure the user has credits.
- 403 on platform calls: Missing role permission (e.g., `manage_apis`, `manage_endpoints`, `manage_routings`).
- CORS/CSRf issues: Ensure `HTTPS_ONLY/HTTPS_ENABLED` and `ALLOWED_ORIGINS`/`COOKIE_DOMAIN` are configured.

## Tips
- Restrict `api_allowed_headers` to exactly what upstream needs.
- Use client routing for blue/green or premium clients via `client-key`.
- Turn on `LOG_FORMAT=json` in prod and ship logs to your SIEM.

