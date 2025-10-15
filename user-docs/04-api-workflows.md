# API Workflows

Real-world examples and end-to-end workflows for publishing and managing APIs through Doorman Gateway.

## Overview

This guide walks through common scenarios:
- Publishing REST APIs with API key injection
- Client-specific routing
- Per-user token management
- GraphQL gateway setup
- SOAP API configuration
- Common errors and troubleshooting

Throughout this guide, the **platform API** lives under `/platform/*` and the **runtime gateway** under `/api/*`.

## Conventions

```bash
BASE=http://localhost:3001        # Backend URL
COOKIE=/tmp/doorman.cookies       # Cookie jar path
```

**Login and check status:**
```bash
# Ensure credentials are set in environment
export DOORMAN_ADMIN_EMAIL="admin@example.com"
export DOORMAN_ADMIN_PASSWORD="YourStrongPassword123!"

# Login
curl -s -c "$COOKIE" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DOORMAN_ADMIN_EMAIL\",\"password\":\"$DOORMAN_ADMIN_PASSWORD\"}" \
  "$BASE/platform/authorization"

# Check status
curl -s -b "$COOKIE" "$BASE/platform/authorization/status"
```

---

## Workflow 1: Publish a REST API with API Key Injection

**Scenario:** Publish `/api/rest/customers/v1/*` backed by `http://httpbin.org`, inject `x-api-key` on outbound calls, and validate request payloads.

### Step 1: Define a Token Group

Token groups manage API keys for upstream services and credit limits.

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit" -d '{
    "api_credit_group": "demo-customers",
    "api_key": "demo-secret-123",
    "api_key_header": "x-api-key",
    "credit_tiers": [
      {
        "tier_name": "default",
        "credits": 999999,
        "input_limit": 0,
        "output_limit": 0,
        "reset_frequency": "monthly"
      }
    ]
  }'
```

**What this does:**
- Creates a credit group called `demo-customers`
- Stores the upstream API key `demo-secret-123`
- Configures Doorman to inject this key as `x-api-key` header
- Provides 999,999 credits that reset monthly

### Step 2: Create the API

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "api_description": "Demo customers API",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["http://httpbin.org"],
    "api_type": "REST",
    "api_allowed_retry_count": 0,
    "api_allowed_headers": ["content-type", "accept"],
    "api_credits_enabled": true,
    "api_credit_group": "demo-customers"
  }'
```

**Key parameters:**
- `api_name` + `api_version`: Unique identifier for the API
- `api_servers`: Upstream server pool
- `api_allowed_headers`: Restrict headers sent to upstream (security)
- `api_credits_enabled` + `api_credit_group`: Enable credit tracking and API key injection

### Step 3: Add Endpoints

Only endpoints you explicitly add will be accessible through the gateway.

```bash
# GET endpoint
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "endpoint_method": "GET",
    "endpoint_uri": "/get",
    "endpoint_description": "Echo GET request"
  }'

# POST endpoint
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "endpoint_method": "POST",
    "endpoint_uri": "/post",
    "endpoint_description": "Echo POST request"
  }'
```

### Step 4: Add Request Validation (Optional)

Attach JSON schema validation to endpoints to reject invalid requests before they hit the upstream.

```bash
# First, get the endpoint_id (via UI or endpoint listing)
# Then attach validation schema

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint/endpoint/validation" -d '{
    "endpoint_id": "<endpoint_id>",
    "validation_enabled": true,
    "validation_schema": {
      "validation_schema": {
        "user.name": {"required": true, "type": "string", "min": 2},
        "user.email": {"required": true, "type": "string", "format": "email"}
      }
    }
  }'
```

**Benefits:**
- Validation failures return HTTP 400 without hitting upstream
- Reduces load on backend services
- Provides consistent error messages

### Step 5: Subscribe Your User

Users must subscribe to an API before they can call it.

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "admin",
    "api_name": "customers",
    "api_version": "v1"
  }'
```

### Step 6: Call the Gateway

Doorman automatically injects the `x-api-key` header to the upstream service.

```bash
# GET request
curl -s -b "$COOKIE" "$BASE/api/rest/customers/v1/get?demo=1"

# POST request (with validation)
curl -s -b "$COOKIE" -H 'Content-Type: application/json' \
  -d '{"user": {"name": "Alice", "email": "alice@example.com"}}' \
  "$BASE/api/rest/customers/v1/post"
```

**What happens:**
1. Doorman validates authentication (cookie)
2. Checks user subscription to `customers/v1`
3. Validates request payload against schema (if enabled)
4. Injects `x-api-key: demo-secret-123` header
5. Proxies request to `http://httpbin.org/post`
6. Returns response to client

---

## Workflow 2: Client-Specific Routing

**Scenario:** Route different clients to different upstream server pools using a `client-key` header.

**Use cases:**
- Blue/green deployments
- Premium tier routing
- Multi-tenant backends
- A/B testing

### Step 1: Create Routing Entries

```bash
# Enterprise client routing
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/routing" -d '{
    "routing_name": "customers-enterprise",
    "routing_servers": ["http://premium-upstream-a:8080", "http://premium-upstream-b:8080"],
    "routing_description": "Premium pool for enterprise clients",
    "client_key": "enterprise-A"
  }'

# Free tier client routing
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/routing" -d '{
    "routing_name": "customers-free",
    "routing_servers": ["http://shared-upstream:8080"],
    "routing_description": "Shared pool for free tier",
    "client_key": "free-tier"
  }'
```

### Step 2: Call Gateway with Client Key

```bash
# Enterprise client (routed to premium pool)
curl -s -b "$COOKIE" -H 'client-key: enterprise-A' \
  "$BASE/api/rest/customers/v1/get"

# Free tier client (routed to shared pool)
curl -s -b "$COOKIE" -H 'client-key: free-tier' \
  "$BASE/api/rest/customers/v1/get"

# No client key (uses default API servers)
curl -s -b "$COOKIE" \
  "$BASE/api/rest/customers/v1/get"
```

**Server selection precedence:**
1. **Routing** (client-specific) - Highest priority
2. **Endpoint-level servers** - Medium priority
3. **API-level servers** - Fallback

---

## Workflow 3: Per-User Token Management

**Scenario:** Track per-user credits for paid APIs and inject user-specific API keys.

**Use cases:**
- SaaS with usage-based billing
- Freemium models with credit limits
- Per-customer API key management

### Step 1: Define Token Group

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit" -d '{
    "api_credit_group": "openai-api",
    "api_key": "default-openai-key",
    "api_key_header": "Authorization",
    "credit_tiers": [
      {
        "tier_name": "free",
        "credits": 1000,
        "input_limit": 100,
        "output_limit": 100,
        "reset_frequency": "monthly"
      },
      {
        "tier_name": "premium",
        "credits": 100000,
        "input_limit": 10000,
        "output_limit": 10000,
        "reset_frequency": "monthly"
      }
    ]
  }'
```

### Step 2: Assign User-Specific API Key

User-specific keys override the group default.

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit/alice" -d '{
    "api_credit_group": "openai-api",
    "api_key": "ALICE-PERSONAL-OPENAI-KEY",
    "api_key_header": "Authorization",
    "credit_tiers": [
      {
        "tier_name": "premium",
        "credits": 100000,
        "input_limit": 10000,
        "output_limit": 10000,
        "reset_frequency": "monthly"
      }
    ]
  }'
```

### Step 3: Create API with Credits Enabled

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "openai",
    "api_version": "v1",
    "api_description": "OpenAI API proxy",
    "api_allowed_roles": ["user", "admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["https://api.openai.com"],
    "api_type": "REST",
    "api_credits_enabled": true,
    "api_credit_group": "openai-api",
    "api_allowed_headers": ["content-type", "authorization"]
  }'
```

### Step 4: Call Gateway

When Alice calls the gateway:
- Doorman injects her personal API key
- Deducts credits from her account
- Returns 401 with error code `GTW008` when credits run out

```bash
# Alice's call (uses her personal key and credits)
curl -s -b "$COOKIE" -H 'Content-Type: application/json' \
  -d '{"prompt": "Hello world"}' \
  "$BASE/api/rest/openai/v1/completions"
```

**Credit tracking:**
- Input/output tokens counted against limits
- Credits reset based on `reset_frequency`
- View credit usage via `/platform/credit/{username}`

---

## Workflow 4: GraphQL Gateway

**Scenario:** Proxy a public GraphQL API with optional validation.

**Gateway path:** `/api/graphql/{apiName}`

**Required header:** `X-API-Version: v1`

### Step 1: Create GraphQL API

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "countries",
    "api_version": "v1",
    "api_description": "Public GraphQL API for country data",
    "api_allowed_roles": ["admin", "user"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["https://countries.trevorblades.com"],
    "api_type": "GraphQL",
    "api_allowed_headers": ["content-type"],
    "api_allowed_retry_count": 0
  }'
```

### Step 2: Subscribe User

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "admin",
    "api_name": "countries",
    "api_version": "v1"
  }'
```

### Step 3: Call GraphQL Gateway

```bash
curl -s -b "$COOKIE" \
  -H 'Content-Type: application/json' \
  -H 'X-API-Version: v1' \
  -d '{"query":"{ country(code: \"US\") { name capital currency } }"}' \
  "$BASE/api/graphql/countries"
```

**Optional: Add GraphQL validation**

Attach validation to verify operation shape and variables:

```json
{
  "api_validation_enabled": true,
  "api_validation_schema": {
    "query": {"required": true, "type": "string"},
    "variables": {"required": false, "type": "object"}
  }
}
```

---

## Workflow 5: SOAP Gateway

**Scenario:** Proxy legacy SOAP APIs with XML validation.

**Gateway path:** `/api/soap/{path}`

### Step 1: Create SOAP API

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "legacy-orders",
    "api_version": "v1",
    "api_description": "Legacy SOAP order service",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["internal"],
    "api_servers": ["http://legacy-soap.internal:8080"],
    "api_type": "SOAP",
    "api_allowed_retry_count": 1,
    "api_allowed_headers": ["content-type", "soapaction"]
  }'
```

### Step 2: Add SOAP Endpoints

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "legacy-orders",
    "api_version": "v1",
    "endpoint_method": "POST",
    "endpoint_uri": "/OrderService/CreateOrder",
    "endpoint_description": "SOAP CreateOrder operation"
  }'
```

### Step 3: Add XML Validation (Optional)

```bash
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint/endpoint/validation" -d '{
    "endpoint_id": "<endpoint_id>",
    "validation_enabled": true,
    "validation_schema": {
      "validation_schema": {
        "orderId": {"required": true, "type": "string"},
        "customerId": {"required": true, "type": "string"}
      }
    }
  }'
```

### Step 4: Call SOAP Gateway

```bash
curl -s -b "$COOKIE" \
  -H 'Content-Type: text/xml' \
  -H 'SOAPAction: CreateOrder' \
  -d '<soap:Envelope>...</soap:Envelope>' \
  "$BASE/api/soap/legacy-orders/v1/OrderService/CreateOrder"
```

---

## Monitoring and Health Checks

### Health Endpoints

```bash
# Liveness probe (basic health)
curl -s "$BASE/platform/monitor/liveness"
# Returns: {"status": "alive"}

# Readiness probe (checks Redis/MongoDB)
curl -s "$BASE/platform/monitor/readiness"
# Returns: {"status": "ready", "mongodb": "connected", "redis": "connected"}

# Gateway status (public endpoint)
curl -s "$BASE/api/health"
# Returns: {"status": "ok", "uptime": 12345, "memory": {...}}
```

### Metrics

```bash
# Requires authentication + manage_gateway permission
curl -s -b "$COOKIE" "$BASE/platform/monitor/metrics?range=24h"
```

**Metrics include:**
- Request counts per API
- Average response times
- Error rates
- Credit usage
- Rate limit hits

### Logs

**Via UI:** Navigate to Logging section

**Via API:**
```bash
# View logs (requires view_logs permission)
curl -s -b "$COOKIE" "$BASE/platform/logging/logs?limit=100"

# Export logs (requires export_logs permission)
curl -s -b "$COOKIE" "$BASE/platform/logging/export?start_date=2024-01-01"
```

**Log files:**
- `backend-services/logs/doorman.log` - Main application log
- `backend-services/logs/doorman-trail.log` - Audit trail

---

## Common Errors and Troubleshooting

### GTW001: API Not Found

**Error message:** "API not found"

**Causes:**
- API with that name/version doesn't exist
- Typo in `api_name` or `api_version`

**Solutions:**
```bash
# List all APIs
curl -s -b "$COOKIE" "$BASE/platform/api"

# Check API details
curl -s -b "$COOKIE" "$BASE/platform/api/customers/v1"
```

### GTW002: No Endpoints Defined

**Error message:** "No endpoints defined for this API"

**Causes:**
- API created but no endpoints added

**Solutions:**
```bash
# Add at least one endpoint
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "customers",
    "api_version": "v1",
    "endpoint_method": "GET",
    "endpoint_uri": "/health"
  }'
```

### GTW003: Endpoint Not Found

**Error message:** "Endpoint not found: GET /users"

**Causes:**
- Method/URI combination not added as an endpoint
- Typo in path or method

**Solutions:**
```bash
# List endpoints for API
curl -s -b "$COOKIE" "$BASE/platform/endpoint?api_name=customers&api_version=v1"

# Check URI matches exactly (including leading slash)
# Gateway path: /api/rest/customers/v1/users
# Endpoint URI should be: /users
```

### GTW008: No Credits/Tokens

**Error message:** "No credits available"

**Causes:**
- User ran out of credits
- No token group assigned
- Credits not enabled for API

**Solutions:**
```bash
# Check user's credits
curl -s -b "$COOKIE" "$BASE/platform/credit/{username}"

# Add more credits
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit/{username}" -d '{
    "api_credit_group": "demo-api",
    "credit_tiers": [{"tier_name": "default", "credits": 100000, ...}]
  }'
```

### HTTP 403: Permission Denied

**Error message:** "You do not have permission..."

**Causes:**
- User lacks required role permission
- User not in allowed group for API
- User not subscribed to API

**Solutions:**
```bash
# Check user's roles
curl -s -b "$COOKIE" "$BASE/platform/user/{username}"

# Add required role
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/user/{username}/roles" -d '{
    "roles": ["manage_apis"]
  }'

# Subscribe to API
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "alice",
    "api_name": "customers",
    "api_version": "v1"
  }'
```

### CORS Errors

**Error:** "CORS policy: No 'Access-Control-Allow-Origin' header"

**Causes:**
- Client origin not in `ALLOWED_ORIGINS`
- Wildcard origin with credentials enabled

**Solutions:**
```bash
# Update environment variable
ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
CORS_STRICT=true

# Use CORS checker tool
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/tools/cors/check" -d '{
    "origin": "https://app.example.com",
    "method": "GET",
    "with_credentials": true
  }'
```

### CSRF Errors

**Error:** "Invalid CSRF token"

**Causes:**
- `X-CSRF-Token` header missing
- CSRF token doesn't match cookie
- HTTPS not properly configured

**Solutions:**
```bash
# Ensure HTTPS is enabled
HTTPS_ONLY=true  # or HTTPS_ENABLED=true

# Include CSRF token in request
curl -s -b "$COOKIE" \
  -H "X-CSRF-Token: $(grep csrf_token cookies.txt | awk '{print $7}')" \
  -H 'Content-Type: application/json' \
  -X POST "$BASE/platform/api" -d '{...}'
```

### Request Too Large (413)

**Error code:** `REQ001`

**Causes:**
- Request body exceeds `MAX_BODY_SIZE_BYTES`

**Solutions:**
```bash
# Increase limit for specific API type
MAX_BODY_SIZE_BYTES_SOAP=2097152  # 2MB for SOAP
MAX_BODY_SIZE_BYTES_REST=524288   # 512KB for REST

# Or increase global limit
MAX_BODY_SIZE_BYTES=2097152
```

---

## Tips and Best Practices

### API Configuration

- **Restrict headers:** Only allow headers that upstream needs via `api_allowed_headers`
- **Use retries wisely:** Set `api_allowed_retry_count` based on upstream idempotency
- **Enable validation:** Validate requests at the gateway to protect upstream services
- **Version APIs:** Always use explicit versions (v1, v2, etc.)

### Routing

- **Client routing:** Use `client-key` header for blue/green deployments or premium tiers
- **Server pools:** Provide multiple servers in `api_servers` for load balancing
- **Precedence:** Remember routing > endpoint > API server selection

### Security

- **Subscribe users:** Always require subscriptions to control access
- **Use groups:** Organize users into groups for easier access management
- **Enable credits:** Track and limit usage with credit system
- **Validate inputs:** Add endpoint validation to reject malformed requests early

### Monitoring

- **Enable JSON logs:** Set `LOG_FORMAT=json` in production
- **Ship to SIEM:** Forward logs to centralized log management
- **Monitor metrics:** Regularly review `/platform/monitor/metrics`
- **Set up alerts:** Alert on error rates, credit exhaustion, rate limit hits

### Performance

- **Use Redis:** Enable Redis for distributed rate limiting and caching
- **Connection pooling:** Upstream servers are pooled automatically
- **Limit body sizes:** Set appropriate `MAX_BODY_SIZE_BYTES` per API type
- **Enable compression:** Configure upstream responses with compression

---

## Next Steps

- **[Configuration Reference](./02-configuration.md)** - Complete environment variable guide
- **[Security Guide](./03-security.md)** - Hardening and security best practices
- **[Operations Guide](./05-operations.md)** - Production deployment and runbooks
- **[Tools](./06-tools.md)** - CORS checker and diagnostics
