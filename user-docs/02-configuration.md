# Configuration Reference

Complete reference for all Doorman environment variables and configuration options.

## Configuration File

All configuration is managed through environment variables, typically stored in a `.env` file in the `backend-services/` directory.

## Core Application Settings

### `ENV`
- **Default:** `development`
- **Values:** `development`, `production`
- **Description:** Application environment. When set to `production`, enforces HTTPS requirements.

### `PORT`
- **Default:** `5001`
- **Description:** Port on which the backend service listens.

### `THREADS`
- **Default:** `4`
- **Description:** Number of worker threads. Set to `1` in memory-only mode to prevent state divergence.

### `DEV_RELOAD`
- **Default:** `False`
- **Description:** Enable auto-reload on code changes. Useful during development.

### `PID_FILE`
- **Default:** `doorman.pid`
- **Description:** Path to PID file for process management.

---

## Admin Credentials

### `DOORMAN_ADMIN_EMAIL`
- **Required:** Yes
- **Description:** Email address for the initial admin user. Used for auto-creation in memory mode.

### `DOORMAN_ADMIN_PASSWORD`
- **Required:** Yes
- **Description:** Password for the initial admin user. Must be at least 12 characters. Use a strong, unique password.

---

## Cache and Database Configuration

### `MEM_OR_EXTERNAL`
- **Default:** `MEM`
- **Values:** `MEM`, `REDIS`
- **Description:** Unified cache/DB mode flag.
  - `MEM`: In-memory cache with optional encrypted dumps to disk
  - `REDIS`: Redis-backed cache with optional MongoDB for persistence
- **Alias:** `MEM_OR_REDIS` (deprecated but still supported)

### Memory Mode Settings

#### `MEM_ENCRYPTION_KEY`
- **Required:** Yes (when using memory dumps)
- **Description:** 32+ character secret for encrypting memory dumps. Required for dump/restore functionality.

#### `MEM_DUMP_PATH`
- **Default:** `backend-services/generated/memory_dump.bin`
- **Description:** Base path for encrypted memory dumps. Timestamp is appended to filename.

### Redis Settings

#### `REDIS_HOST`
- **Default:** `localhost`
- **Description:** Redis server hostname or IP.

#### `REDIS_PORT`
- **Default:** `6379`
- **Description:** Redis server port.

#### `REDIS_DB`
- **Default:** `0`
- **Description:** Redis database number.

### MongoDB Settings

#### `MONGO_DB_HOSTS`
- **Default:** `localhost:27017`
- **Description:** Comma-separated list of MongoDB hosts for replica set.

#### `MONGO_REPLICA_SET_NAME`
- **Default:** `rs0`
- **Description:** MongoDB replica set name. Required for production high-availability.

---

## Security and Authentication

### JWT Configuration

#### `JWT_SECRET_KEY`
- **Required:** Yes
- **Description:** Secret key for signing JWT tokens. **Gateway will fail to start if not set.** Use a strong, random value (32+ characters). Rotate periodically.

#### `AUTH_EXPIRE_TIME`
- **Default:** `30`
- **Description:** Access token expiration time (numeric value).

#### `AUTH_EXPIRE_TIME_FREQ`
- **Default:** `minutes`
- **Values:** `seconds`, `minutes`, `hours`, `days`
- **Description:** Access token expiration frequency.

#### `AUTH_REFRESH_EXPIRE_TIME`
- **Default:** `7`
- **Description:** Refresh token expiration time (numeric value).

#### `AUTH_REFRESH_EXPIRE_FREQ`
- **Default:** `days`
- **Values:** `seconds`, `minutes`, `hours`, `days`
- **Description:** Refresh token expiration frequency.

### Encryption Keys

#### `TOKEN_ENCRYPTION_KEY`
- **Recommended:** Yes
- **Description:** Secret key for encrypting API keys at rest. Provides additional security layer for stored credentials.

#### `MEM_ENCRYPTION_KEY`
- **Required:** Yes (for memory dumps)
- **Description:** Secret key for encrypting memory dumps. Must be 32+ characters.

---

## HTTPS and TLS Configuration

### `HTTPS_ONLY`
- **Default:** `False`
- **Description:** When `true`, Doorman terminates TLS itself and enforces HTTPS. Sets `Secure` flag on cookies and sends HSTS headers. **Required in production** unless `HTTPS_ENABLED=true`.

### `HTTPS_ENABLED`
- **Default:** `False`
- **Description:** When `true`, assumes TLS is terminated at a reverse proxy. Enables secure cookies and CSRF validation even though Doorman listens on HTTP. **Required in production** unless `HTTPS_ONLY=true`.

### `SSL_CERTFILE`
- **Required:** When `HTTPS_ONLY=true`
- **Example:** `./certs/fullchain.pem`
- **Description:** Path to TLS certificate file.

### `SSL_KEYFILE`
- **Required:** When `HTTPS_ONLY=true`
- **Example:** `./certs/privkey.pem`
- **Description:** Path to TLS private key file.

---

## CORS Configuration

### `ALLOWED_ORIGINS`
- **Default:** `*`
- **Example:** `https://admin.example.com,https://app.example.com`
- **Description:** Comma-separated list of allowed origins. **Do not use wildcard `*` in production** with credentials.

### `ALLOW_CREDENTIALS`
- **Default:** `False`
- **Description:** Allow credentials (cookies, Authorization headers) in CORS requests. Only set to `True` with explicit origins.

### `ALLOW_METHODS`
- **Default:** `GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD`
- **Description:** Comma-separated list of allowed HTTP methods.

### `ALLOW_HEADERS`
- **Default:** `*`
- **Description:** Comma-separated list of allowed request headers. Use `*` for all, or specify explicitly.

### `CORS_STRICT`
- **Default:** `False`
- **Description:** When `true`, disallows wildcard origins when credentials are enabled. **Recommended for production.**

### `COOKIE_DOMAIN`
- **Default:** `localhost`
- **Description:** Domain for which cookies are valid. Must match your site's hostname for secure cookies to work.

---

## Security Headers

### `CONTENT_SECURITY_POLICY`
- **Default:** `default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; img-src 'self' data:; connect-src 'self';`
- **Description:** Content Security Policy header value. Override to customize CSP rules.

---

## IP Access Control

### `LOCAL_HOST_IP_BYPASS`
- **Default:** `False`
- **Description:** When `true`, requests from `127.0.0.1`/`::1` bypass IP allow/deny lists. **Disable in production.**

### Platform IP Settings (via API/UI)

These are configured via the Security Settings API or UI, not environment variables:

- **`ip_whitelist`**: List of allowed IP addresses/CIDRs. If set, only these IPs can access the platform.
- **`ip_blacklist`**: List of denied IP addresses/CIDRs. Evaluated after whitelist.
- **`trust_x_forwarded_for`**: Trust client IP headers (`X-Forwarded-For`, `X-Real-IP`, `CF-Connecting-IP`).
- **`xff_trusted_proxies`**: List of trusted proxy IPs. **Required when `trust_x_forwarded_for=true`** to prevent spoofing.

---

## Request Limits

### `MAX_BODY_SIZE_BYTES`
- **Default:** `1048576` (1MB)
- **Description:** Global maximum request body size in bytes. Prevents DoS via large payloads.

### `MAX_BODY_SIZE_BYTES_REST`
- **Optional**
- **Description:** Override for REST API requests (`/api/rest/*`).

### `MAX_BODY_SIZE_BYTES_SOAP`
- **Optional**
- **Example:** `2097152` (2MB)
- **Description:** Override for SOAP/XML API requests (`/api/soap/*`). SOAP envelopes can be larger.

### `MAX_BODY_SIZE_BYTES_GRAPHQL`
- **Optional**
- **Example:** `524288` (512KB)
- **Description:** Override for GraphQL requests (`/api/graphql/*`).

### `MAX_BODY_SIZE_BYTES_GRPC`
- **Optional**
- **Description:** Override for gRPC requests (`/api/grpc/*`).

### `MAX_MULTIPART_SIZE_BYTES`
- **Default:** `10485760` (10MB)
- **Description:** Maximum size for multipart uploads (e.g., proto file uploads).

---

## Logging Configuration

### `LOG_FORMAT`
- **Default:** `plain`
- **Values:** `plain`, `json`
- **Description:** Log output format. Use `json` in production for structured logging and SIEM ingestion.

### `LOG_LEVEL`
- **Default:** `INFO`
- **Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description:** Minimum log level to output.

---

## HTTP Resilience

Configure upstream HTTP behavior (timeouts, retries, and circuit breaker).

### Timeouts

- `HTTP_CONNECT_TIMEOUT` (default: `5.0`) - Seconds to establish a TCP connection
- `HTTP_READ_TIMEOUT` (default: `30.0`) - Seconds to read the response body
- `HTTP_WRITE_TIMEOUT` (default: `30.0`) - Seconds to write the request body
- `HTTP_TIMEOUT` (default: `30.0`) - Pool acquire timeout

Per‑API overrides are supported via API configuration fields:
- `api_connect_timeout`, `api_read_timeout`, `api_write_timeout`, `api_pool_timeout`

### Retries (jittered exponential backoff)

- `HTTP_RETRY_BASE_DELAY` (default: `0.25`) - Base delay in seconds
- `HTTP_RETRY_MAX_DELAY` (default: `2.0`) - Maximum backoff delay cap
- Retries are configured per API with `api_allowed_retry_count` (0 = no retries)

### Circuit Breaker

- `CIRCUIT_BREAKER_ENABLED` (default: `true`) - Enable the breaker
- `CIRCUIT_BREAKER_THRESHOLD` (default: `5`) - Failures before opening
- `CIRCUIT_BREAKER_TIMEOUT` (default: `30`) - Seconds to stay open before half‑open probing

Behavior:
- On transient 5xx or network/timeout failures, the breaker counts failures.
- When threshold is reached, the circuit opens and upstream calls fail fast.
- After timeout, half‑open allows a probe; success closes, failure re‑opens.

---

## Response Envelope

### `STRICT_RESPONSE_ENVELOPE`
- **Default:** `False`
- **Description:** When `true`, platform API responses use a consistent envelope structure for all responses (success, error, created).

**Example responses when enabled:**

Success (200):
```json
{
  "status_code": 200,
  "response": { "key": "value" }
}
```

Created (201):
```json
{
  "status_code": 201,
  "message": "Resource created successfully"
}
```

Error (403):
```json
{
  "status_code": 403,
  "error_code": "ROLE009",
  "error_message": "You do not have permission to create roles"
}
```

---

## Configuration Examples

### Development Configuration

```bash
# .env (development)
ENV=development
PORT=5001
THREADS=4
DEV_RELOAD=True

DOORMAN_ADMIN_EMAIL=admin@localhost
DOORMAN_ADMIN_PASSWORD=DevPassword123!

MEM_OR_EXTERNAL=MEM
MEM_ENCRYPTION_KEY=dev-only-secret-32chars-minimum-length

JWT_SECRET_KEY=dev-jwt-secret-change-in-production
TOKEN_ENCRYPTION_KEY=dev-token-encryption-key

ALLOWED_ORIGINS=http://localhost:3000
ALLOW_CREDENTIALS=True
HTTPS_ONLY=False
COOKIE_DOMAIN=localhost

LOG_FORMAT=plain
LOG_LEVEL=DEBUG
```

### Production Configuration

```bash
# .env (production)
ENV=production
PORT=5001
THREADS=4
DEV_RELOAD=False

DOORMAN_ADMIN_EMAIL=admin@yourdomain.com
DOORMAN_ADMIN_PASSWORD=StrongProductionPassword123!@#

# HTTPS (REQUIRED in production)
HTTPS_ONLY=True
SSL_CERTFILE=/certs/fullchain.pem
SSL_KEYFILE=/certs/privkey.pem

# Secrets (use strong, random values)
JWT_SECRET_KEY=${JWT_SECRET_FROM_VAULT}
TOKEN_ENCRYPTION_KEY=${TOKEN_ENCRYPTION_FROM_VAULT}
MEM_ENCRYPTION_KEY=${MEM_ENCRYPTION_FROM_VAULT}

# Cache and Database
MEM_OR_EXTERNAL=REDIS
REDIS_HOST=redis.internal
REDIS_PORT=6379
REDIS_DB=0
MONGO_DB_HOSTS=mongo1.internal:27017,mongo2.internal:27017,mongo3.internal:27017
MONGO_REPLICA_SET_NAME=rs0

# CORS (strict)
ALLOWED_ORIGINS=https://admin.yourdomain.com,https://api.yourdomain.com
ALLOW_CREDENTIALS=True
CORS_STRICT=True
COOKIE_DOMAIN=yourdomain.com

# Request limits
MAX_BODY_SIZE_BYTES=1048576
MAX_BODY_SIZE_BYTES_SOAP=2097152

# Logging
LOG_FORMAT=json
LOG_LEVEL=INFO

# Security
STRICT_RESPONSE_ENVELOPE=True
LOCAL_HOST_IP_BYPASS=False
```

### Production with Reverse Proxy

```bash
# .env (production behind proxy)
ENV=production
PORT=5001

# HTTPS terminated at proxy
HTTPS_ENABLED=True  # NOT HTTPS_ONLY
SSL_CERTFILE=      # Not needed
SSL_KEYFILE=       # Not needed

# Rest is same as production config above
JWT_SECRET_KEY=${JWT_SECRET_FROM_VAULT}
TOKEN_ENCRYPTION_KEY=${TOKEN_ENCRYPTION_FROM_VAULT}
ALLOWED_ORIGINS=https://admin.yourdomain.com
CORS_STRICT=True
COOKIE_DOMAIN=yourdomain.com

# Cache and DB
MEM_OR_EXTERNAL=REDIS
REDIS_HOST=redis.internal
MONGO_DB_HOSTS=mongo.internal:27017

LOG_FORMAT=json
```

---

## Configuration Best Practices

### Development
- Use memory mode (`MEM_OR_EXTERNAL=MEM`) for simplicity
- Enable `DEV_RELOAD=True` for faster iteration
- Use `LOG_LEVEL=DEBUG` for detailed output
- Self-signed certificates are acceptable

### Production
- **HTTPS is mandatory**: Set `HTTPS_ONLY=true` or `HTTPS_ENABLED=true`
- Use Redis for distributed rate limiting (`MEM_OR_EXTERNAL=REDIS`)
- Use MongoDB for persistence and high availability
- Set `CORS_STRICT=true` and explicit `ALLOWED_ORIGINS`
- Use `LOG_FORMAT=json` for structured logging
- Store secrets in a secret manager (Vault, AWS Secrets Manager, etc.)
- Rotate `JWT_SECRET_KEY` periodically
- Set `LOCAL_HOST_IP_BYPASS=False`
- Configure IP whitelisting if needed
- Set `THREADS` based on your load (4-8 typically)
- Use Redis (`MEM_OR_EXTERNAL=REDIS`) when running with `THREADS>1` or multiple instances; memory mode with multiple workers is guarded and will fail startup

---

## Request Tracing

- Doorman accepts an incoming `X-Request-ID` or generates one per request.
- The header is forwarded to upstream services and echoed back in responses as `X-Request-ID`.
- To expose additional upstream headers back to clients, include them in your API’s `api_allowed_headers` (e.g., `X-Upstream-Request-ID`).

### Secrets Management
- Never commit secrets to version control
- Use environment-specific `.env` files (`.env.development`, `.env.production`)
- Add `.env*` to `.gitignore` (except `.env.example`)
- Use secret managers in production
- Rotate secrets regularly

---

## Validation on Startup

Doorman validates critical configuration on startup:

- **`JWT_SECRET_KEY` must be set** - Gateway fails fast if missing
- **HTTPS required in production** - Fails if `ENV=production` and neither `HTTPS_ONLY` nor `HTTPS_ENABLED` is true
- **Memory encryption key required for dumps** - Warns if missing when dumps are enabled

---

## Need Help?

- [Getting Started](./01-getting-started.md) - Setup guide
- [Security Guide](./03-security.md) - Security best practices
- [Operations Guide](./05-operations.md) - Production deployment
