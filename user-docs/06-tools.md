# Tools and Diagnostics

Built-in tools for troubleshooting, validation, and diagnostics in Doorman API Gateway.

## Overview

Doorman provides several tools to help operate and troubleshoot your gateway:
- CORS Checker - Validate CORS configuration
- Health Endpoints - Monitor system health
- Metrics API - Track usage and performance
- Log Analysis - Audit trail and request logs
- Validator Audit - Ensure enabled validators have schemas

---

## CORS Checker

Validate your CORS configuration without trial-and-error in a browser. This tool simulates preflight (OPTIONS) and actual requests to show you exactly what would happen.

### Access

**UI:** Navigate to Tools → CORS Checker (requires `manage_security` permission)

**API:** `POST /platform/tools/cors/check` (requires `manage_security`)

### Usage

**Request:**
```bash
curl -s -b cookies.txt \
  -H 'Content-Type: application/json' \
  -X POST https://api.yourdomain.com/platform/tools/cors/check \
  -d '{
    "origin": "https://app.example.com",
    "method": "POST",
    "request_headers": ["Content-Type", "Authorization", "X-Custom-Header"],
    "with_credentials": true
  }'
```

**Response:**
```json
{
  "config": {
    "allowed_origins": ["https://app.example.com", "https://admin.example.com"],
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "allow_credentials": true,
    "cors_strict": true
  },
  "preflight": {
    "allowed": true,
    "headers": {
      "Access-Control-Allow-Origin": "https://app.example.com",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Allow-Credentials": "true",
      "Access-Control-Max-Age": "86400"
    },
    "notes": []
  },
  "actual": {
    "allowed": true,
    "headers": {
      "Access-Control-Allow-Origin": "https://app.example.com",
      "Access-Control-Allow-Credentials": "true",
      "Access-Control-Expose-Headers": "X-Request-ID"
    },
    "notes": []
  },
  "recommendations": [
    "Configuration is valid for the given origin and method."
  ]
}
```

### Response Fields

**`config`** - Effective CORS configuration derived from environment variables:
- `allowed_origins` - List of allowed origins
- `allow_methods` - Allowed HTTP methods
- `allow_headers` - Allowed request headers
- `allow_credentials` - Whether credentials are allowed
- `cors_strict` - Whether strict mode is enabled

**`preflight`** - Preflight (OPTIONS) request simulation:
- `allowed` - Whether preflight would succeed
- `headers` - Response headers that would be sent
- `notes` - Warnings or issues detected

**`actual`** - Actual request simulation:
- `allowed` - Whether the actual request would succeed
- `headers` - Response headers that would be sent
- `notes` - Warnings or issues detected

**`recommendations`** - Actionable advice for fixing issues

### Common Scenarios

#### Scenario 1: Wildcard Origin with Credentials

**Request:**
```json
{
  "origin": "https://app.example.com",
  "method": "GET",
  "with_credentials": true
}
```

**Response (if `ALLOWED_ORIGINS=*`):**
```json
{
  "preflight": {
    "allowed": false,
    "notes": [
      "Wildcard origin '*' cannot be used with credentials. Set explicit origins in ALLOWED_ORIGINS or disable credentials."
    ]
  },
  "recommendations": [
    "Set ALLOWED_ORIGINS to explicit domains: ALLOWED_ORIGINS=https://app.example.com",
    "Or enable CORS_STRICT=true to automatically reject this configuration"
  ]
}
```

#### Scenario 2: Disallowed Header

**Request:**
```json
{
  "origin": "https://app.example.com",
  "method": "POST",
  "request_headers": ["Content-Type", "X-Custom-Header"]
}
```

**Response (if `X-Custom-Header` not in `ALLOW_HEADERS`):**
```json
{
  "preflight": {
    "allowed": false,
    "notes": [
      "Header 'X-Custom-Header' is not in ALLOW_HEADERS"
    ]
  },
  "recommendations": [
    "Add 'X-Custom-Header' to ALLOW_HEADERS environment variable",
    "Or use ALLOW_HEADERS=* to allow all headers (not recommended for production)"
  ]
}
```

#### Scenario 3: Origin Not Allowed

**Request:**
```json
{
  "origin": "https://evil.com",
  "method": "GET"
}
```

**Response (if origin not in `ALLOWED_ORIGINS`):**
```json
{
  "preflight": {
    "allowed": false,
    "notes": [
      "Origin 'https://evil.com' is not in ALLOWED_ORIGINS"
    ]
  },
  "recommendations": [
    "If this origin should be allowed, add it to ALLOWED_ORIGINS: ALLOWED_ORIGINS=https://app.example.com,https://evil.com"
  ]
}
```

### Environment Variables Considered

The CORS checker evaluates these environment variables:

- `ALLOWED_ORIGINS` - Comma-separated list of allowed origins
- `ALLOW_METHODS` - Comma-separated list of allowed methods
- `ALLOW_HEADERS` - Comma-separated list of allowed headers or `*`
- `ALLOW_CREDENTIALS` - Whether to allow credentials (`true` or `false`)
- `CORS_STRICT` - Reject wildcard with credentials (`true` or `false`)

### Tips

**Avoid wildcards in production:**
```bash
# Bad (insecure with credentials)
ALLOWED_ORIGINS=*
ALLOW_CREDENTIALS=True

# Good (explicit origins)
ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com
ALLOW_CREDENTIALS=True
CORS_STRICT=true
```

---

## Validator Activation Audit

Validate that every endpoint with `validation_enabled=true` has a non‑empty `validation_schema`.

### Purpose

- Prevents silent misconfiguration where validation is enabled but no schema is present.

### How to Run

- A test is included: `backend-services/tests/test_validation_audit.py`.
- Run it with your test runner, or adapt the logic to a CI job to block merges when audits fail.

### What It Checks

- Iterates endpoint validations where `validation_enabled=true`.
- Asserts referenced endpoint exists.
- Asserts `validation_schema` is a non‑empty object.

### Remediation

- For each failing entry, either:
  - Provide a valid `validation_schema`, or
  - Disable validation until a schema is ready.

**Conservative header policy:**
```bash
# Instead of:
ALLOW_HEADERS=*

# Use explicit list:
ALLOW_HEADERS=Content-Type,Authorization,X-CSRF-Token
```

**Enable strict mode:**
```bash
CORS_STRICT=true  # Rejects wildcard with credentials automatically
```

---

## Health and Monitoring Endpoints

### Liveness Probe

**Endpoint:** `GET /platform/monitor/liveness`

**Purpose:** Basic health check - is the application running?

**Response:**
```json
{
  "status": "alive"
}
```

**HTTP Status:** Always returns 200 if process is running

**Use case:** Kubernetes liveness probe, basic uptime monitoring

**Example:**
```bash
curl -s https://api.yourdomain.com/platform/monitor/liveness
```

### Readiness Probe

**Endpoint:** `GET /platform/monitor/readiness`

**Purpose:** Check if application is ready to serve traffic (includes dependency checks)

**Response (healthy):**
```json
{
  "status": "ready",
  "mongodb": "connected",
  "redis": "connected",
  "checks": {
    "database": "pass",
    "cache": "pass"
  }
}
```

**Response (degraded):**
```json
{
  "status": "degraded",
  "mongodb": "disconnected",
  "redis": "connected",
  "checks": {
    "database": "fail",
    "cache": "pass"
  }
}
```

**HTTP Status:**
- `200` - All checks pass
- `503` - One or more checks fail

**Use case:** Kubernetes readiness probe, load balancer health checks

**Example:**
```bash
curl -s https://api.yourdomain.com/platform/monitor/readiness
```

### Gateway Status (Public)

Public health probe: `GET /api/health`

Admin status (requires manage_gateway): `GET /api/status`

**Purpose:** Public status endpoint (no authentication required)

**Response:**
```json
{
  "status": "ok",
  "mode": "redis",
  "uptime_seconds": 86400,
  "memory_usage_mb": 256,
  "version": "1.0.0"
}
```

**Use case:** Public status page, basic monitoring

**Example:**
```bash
curl -s https://api.yourdomain.com/api/health
```

---

## Metrics API

### Get Metrics

**Endpoint:** `GET /platform/monitor/metrics`

**Authentication:** Required (cookie or Bearer token)

**Permission:** `manage_gateway`

**Query Parameters:**
- `range` - Time range: `1h`, `24h`, `7d`, `30d` (default: `24h`)

**Request:**
```bash
curl -s -b cookies.txt \
  'https://api.yourdomain.com/platform/monitor/metrics?range=24h'
```

**Response:**
```json
{
  "period": "24h",
  "start_time": "2024-01-14T10:00:00Z",
  "end_time": "2024-01-15T10:00:00Z",
  "total_requests": 125000,
  "total_errors": 250,
  "error_rate": 0.002,
  "avg_response_time_ms": 45,
  "p50_response_time_ms": 35,
  "p95_response_time_ms": 120,
  "p99_response_time_ms": 250,
  "by_api": {
    "customers/v1": {
      "requests": 50000,
      "errors": 100,
      "error_rate": 0.002,
      "avg_response_time_ms": 40,
      "p95_response_time_ms": 100
    },
    "orders/v1": {
      "requests": 75000,
      "errors": 150,
      "error_rate": 0.002,
      "avg_response_time_ms": 50,
      "p95_response_time_ms": 140
    }
  },
  "by_status_code": {
    "200": 120000,
    "400": 100,
    "401": 50,
    "403": 50,
    "500": 50
  },
  "top_errors": [
    {
      "error_code": "GTW003",
      "count": 100,
      "message": "Endpoint not found"
    },
    {
      "error_code": "GTW008",
      "count": 50,
      "message": "No credits available"
    }
  ]
}
```

### Metrics Dashboard

**UI:** Navigate to Dashboard → Metrics

**Features:**
- Real-time request rate
- Error rate over time
- Response time percentiles
- Top APIs by traffic
- Top errors

---

## Admin CLI (ops/admin_cli.py)

Command‑line helper for common maintenance actions with safety prompts.

### Usage

```bash
# Environment (development defaults shown)
export BASE_URL=http://localhost:5001
export DOORMAN_ADMIN_EMAIL=admin@doorman.dev
export DOORMAN_ADMIN_PASSWORD=your-admin-password

python3 ops/admin_cli.py --help
```

### Commands

- `metrics` — Show `/platform/monitor/metrics` snapshot
- `dump [--path <file>]` — Dump in‑memory DB to encrypted file (memory mode)
- `restore [--path <file>]` — Restore in‑memory DB from encrypted file (memory mode)
- `chaos <redis|mongo> [--enabled] [--duration-ms N]` — Toggle backend outages
- `chaos-stats` — Show chaos stats (`error_budget_burn`)
- `revoke <username>` — Revoke all tokens for a user
- `enable-user <username>` / `disable-user <username>` — Enable/disable a user
- `rotate-admin [--password <new>]` — Rotate admin password

All dangerous operations prompt for confirmation; pass `-y/--yes` to skip prompts.

### Makefile Shortcuts (ops/Makefile)

```bash
# Show metrics
make -C ops metrics

# Dump / restore memory DB (memory-only mode)
make -C ops dump PATH=/tmp/doorman.enc
make -C ops restore PATH=/tmp/doorman.enc

# Chaos toggles
make -C ops chaos-on DURATION=5000
make -C ops chaos-off
make -C ops chaos-stats
```

---

## Chaos Toggles (Tools API)

Simulate backend outages to test resiliency and alerting.

### Enable outage for 5 seconds

```bash
curl -s -b cookies.txt \
  -H 'Content-Type: application/json' \
  -X POST "$BASE/platform/tools/chaos/toggle" \
  -d '{"backend":"redis","enabled":true,"duration_ms":5000}'
```

### Read stats

```bash
curl -s -b cookies.txt "$BASE/platform/tools/chaos/stats"
# { "redis_outage": false, "mongo_outage": false, "error_budget_burn": 12 }
```

Note: Requires `manage_gateway` permission.
- Credit usage

---

## Log Analysis

### Application Logs

**Location:** `backend-services/logs/doorman.log`

**Format:** Plain text or JSON (configured via `LOG_FORMAT`)

**Plain text example:**
```
2024-01-15 10:30:00 INFO [request_id=abc123] GET /api/rest/customers/v1/get - 200 - 45ms
2024-01-15 10:30:01 ERROR [request_id=def456] Failed to connect to upstream: Connection timeout
```

**JSON example:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "request_id": "abc123",
  "method": "GET",
  "path": "/api/rest/customers/v1/get",
  "status_code": 200,
  "response_time_ms": 45,
  "client_ip": "192.168.1.100",
  "username": "admin"
}
```

### Audit Trail

**Location:** `backend-services/logs/doorman-trail.log`

**Format:** Structured events for security and compliance

**Example events:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "abc123",
  "event_type": "auth.login",
  "username": "admin",
  "status": "success",
  "client_ip": "192.168.1.100",
  "effective_ip": "203.0.113.50"
}

{
  "timestamp": "2024-01-15T10:31:00Z",
  "request_id": "def456",
  "event_type": "api.create",
  "username": "admin",
  "action": "create",
  "target": "customers/v1",
  "status": "success",
  "details": {"api_type": "REST"}
}

{
  "timestamp": "2024-01-15T10:32:00Z",
  "request_id": "ghi789",
  "event_type": "ip.global_deny",
  "username": null,
  "client_ip": "1.2.3.4",
  "status": "blocked",
  "details": {"reason": "in_blacklist"}
}
```

**Event types:**
- `auth.login` - User login
- `auth.logout` - User logout
- `auth.refresh` - Token refresh
- `auth.revoke` - Token revocation
- `api.create` - API created
- `api.update` - API updated
- `api.delete` - API deleted
- `endpoint.create` - Endpoint created
- `ip.global_deny` - IP blocked by global policy
- `ip.api_deny` - IP blocked by API policy
- `security.config_change` - Security settings changed

### Viewing Logs via API

**Endpoint:** `GET /platform/logging/logs`

**Authentication:** Required

**Permission:** `view_logs`

**Query Parameters:**
- `limit` - Number of records (default: 100)
- `offset` - Pagination offset
- `level` - Filter by log level (`INFO`, `WARNING`, `ERROR`)
- `start_date` - Start timestamp (ISO 8601)
- `end_date` - End timestamp (ISO 8601)

**Request:**
```bash
curl -s -b cookies.txt \
  'https://api.yourdomain.com/platform/logging/logs?limit=50&level=ERROR'
```

**Response:**
```json
{
  "total": 250,
  "limit": 50,
  "offset": 0,
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "ERROR",
      "request_id": "abc123",
      "message": "Upstream connection timeout",
      "details": {
        "upstream": "http://backend:8080",
        "api": "customers/v1"
      }
    }
  ]
}
```

### Exporting Logs

**Endpoint:** `GET /platform/logging/export`

**Authentication:** Required

**Permission:** `export_logs`

**Query Parameters:**
- `start_date` - Start timestamp (ISO 8601)
- `end_date` - End timestamp (ISO 8601)
- `format` - Export format (`json`, `csv`)

**Request:**
```bash
curl -s -b cookies.txt \
  'https://api.yourdomain.com/platform/logging/export?start_date=2024-01-01&end_date=2024-01-15&format=json' \
  > logs_export.json
```

---

## Diagnostic Commands

### Check Configuration

```bash
# View effective environment config
docker exec doorman-backend env | grep -E 'DOORMAN|REDIS|MONGO|JWT|HTTPS|CORS'
```

### Test Redis Connection

```bash
# Direct test
redis-cli -h redis.internal ping

# Via Docker
docker exec redis redis-cli ping
```

### Test MongoDB Connection

```bash
# Direct test
mongosh --host mongo.internal --eval "db.adminCommand('ping')"

# Via Docker
docker exec mongo mongosh --eval "db.adminCommand('ping')"
```

### View Memory Dumps

```bash
# List memory dumps
ls -lh backend-services/generated/memory_dump*.bin

# Check encryption (should be binary/encrypted)
file backend-services/generated/memory_dump-*.bin
```

### Monitor Request Rate

```bash
# Real-time request log (JSON format)
tail -f logs/doorman.log | grep -o '"path":"[^"]*"' | sort | uniq -c

# Count requests by status code
grep -o '"status_code":[0-9]*' logs/doorman.log | sort | uniq -c
```

### Find High-Latency Requests

```bash
# Find requests taking > 1000ms (JSON logs)
grep '"response_time_ms":[0-9]*' logs/doorman.log | \
  awk -F':' '{if ($NF > 1000) print}' | \
  head -20
```

---

## Troubleshooting Workflows

### Workflow 1: Debug CORS Issues

1. **Use CORS checker tool:**
   ```bash
   POST /platform/tools/cors/check
   ```

2. **Check environment variables:**
   ```bash
   echo $ALLOWED_ORIGINS
   echo $ALLOW_CREDENTIALS
   echo $CORS_STRICT
   ```

3. **Review browser console:**
   - Look for preflight failures
   - Check `Access-Control-*` headers in response

4. **Test with curl:**
   ```bash
   # Preflight request
   curl -X OPTIONS -H "Origin: https://app.example.com" \
     -H "Access-Control-Request-Method: POST" \
     https://api.yourdomain.com/platform/api

   # Actual request
   curl -H "Origin: https://app.example.com" \
     https://api.yourdomain.com/platform/api
   ```

### Workflow 2: Investigate 401 Errors

1. **Check authentication status:**
   ```bash
   curl -b cookies.txt https://api.yourdomain.com/platform/authorization/status
   ```

2. **Review audit logs:**
   ```bash
   grep '"event_type":"auth' logs/doorman-trail.log | tail -20
   ```

3. **Verify user subscription:**
   ```bash
   GET /platform/subscription/{username}
   ```

4. **Check token expiration:**
   ```bash
   # Access token expires in 30 minutes by default
   # Check AUTH_EXPIRE_TIME and AUTH_EXPIRE_TIME_FREQ
   ```

### Workflow 3: Debug Upstream Errors

1. **Check API configuration:**
   ```bash
   curl -b cookies.txt https://api.yourdomain.com/platform/api/customers/v1
   ```

2. **Verify upstream servers:**
   ```bash
   # Test connectivity
   curl -v http://backend:8080/health
   ```

3. **Review error logs:**
   ```bash
   grep 'upstream' logs/doorman.log | grep ERROR | tail -20
   ```

4. **Check retry configuration:**
   ```json
   {
     "api_allowed_retry_count": 1  # Increase if upstream is flaky
   }
   ```

---

## Performance Profiling

### Response Time Analysis

```bash
# Get p50, p95, p99 response times
curl -s -b cookies.txt \
  'https://api.yourdomain.com/platform/monitor/metrics?range=24h' | \
  jq '{p50: .p50_response_time_ms, p95: .p95_response_time_ms, p99: .p99_response_time_ms}'
```

### Identify Slow APIs

```bash
# Sort APIs by average response time
curl -s -b cookies.txt \
  'https://api.yourdomain.com/platform/monitor/metrics?range=24h' | \
  jq '.by_api | to_entries | sort_by(.value.avg_response_time_ms) | reverse | .[:5]'
```

### Memory Usage Monitoring

```bash
# Check gateway status for memory usage
# Admins can fetch detailed status
curl -s -b access_token_cookie=... https://api.yourdomain.com/api/status | jq '.memory_usage'
```

---

## Next Steps

- **[Configuration Reference](./02-configuration.md)** - Environment variables
- **[Security Guide](./03-security.md)** - Hardening and security
- **[API Workflows](./04-api-workflows.md)** - Real-world examples
- **[Operations Guide](./05-operations.md)** - Production deployment
