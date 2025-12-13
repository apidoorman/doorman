# API Workflows

End-to-end examples for common API gateway scenarios.

## Setup

```bash
export BASE=http://localhost:3001
export COOKIE=/tmp/doorman.cookies
export DOORMAN_ADMIN_EMAIL="admin@example.com"
export DOORMAN_ADMIN_PASSWORD="YourStrongPassword123!"

# Login once
curl -sc "$COOKIE" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DOORMAN_ADMIN_EMAIL\",\"password\":\"$DOORMAN_ADMIN_PASSWORD\"}" \
  "$BASE/platform/authorization"
```

---

## Workflow 1: REST API with API Key Injection

Publish `/api/rest/customers/v1/*` → `http://httpbin.org` with automatic API key injection.

```bash
# 1) Create token group
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit" -d '{
    "api_credit_group": "demo-customers",
    "api_key": "demo-secret-123",
    "api_key_header": "x-api-key",
    "credit_tiers": [{"tier_name": "default", "credits": 999999, "reset_frequency": "monthly"}]
  }'

# 2) Create API
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "api_description": "Demo customers API",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["http://httpbin.org"],
    "api_type": "REST",
    "api_credits_enabled": true,
    "api_credit_group": "demo-customers"
  }'

# 3) Add endpoints
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "endpoint_method": "GET",
    "endpoint_uri": "/get"
  }'

# 4) Subscribe user
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "admin",
    "api_name": "customers",
    "api_version": "v1"
  }'

# 5) Test
curl -sb "$COOKIE" "$BASE/api/rest/customers/v1/get?demo=1"
```

---

## Workflow 2: Client-Specific Routing

Route clients to different upstream pools via `client-key` header.

```bash
# Enterprise routing
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/routing" -d '{
    "routing_name": "customers-enterprise",
    "routing_servers": ["http://premium-upstream-a:8080", "http://premium-upstream-b:8080"],
    "client_key": "enterprise-A"
  }'

# Free tier routing
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/routing" -d '{
    "routing_name": "customers-free",
    "routing_servers": ["http://shared-upstream:8080"],
    "client_key": "free-tier"
  }'

# Test
curl -sb "$COOKIE" -H 'client-key: enterprise-A' "$BASE/api/rest/customers/v1/get"
curl -sb "$COOKIE" -H 'client-key: free-tier' "$BASE/api/rest/customers/v1/get"
```

---

## Workflow 3: Per-User Token Management

Track per-user credits and inject user-specific API keys.

```bash
# Create token group
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit" -d '{
    "api_credit_group": "openai-api",
    "api_key": "default-openai-key",
    "api_key_header": "Authorization",
    "credit_tiers": [{"tier_name": "free", "credits": 1000, "reset_frequency": "monthly"}]
  }'

# Assign personal key to user 'alice'
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit/alice" -d '{
    "api_credit_group": "openai-api",
    "api_key": "ALICE-PERSONAL-OPENAI-KEY",
    "api_key_header": "Authorization",
    "credit_tiers": [{"tier_name": "premium", "credits": 100000, "reset_frequency": "monthly"}]
  }'
```
