# Configuration Reference

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `development` | `development` or `production`. Production enforces HTTPS |
| `PORT` | `3001` | Backend API port |
| `WEB_PORT` | `3000` | Frontend port (Docker only) |
| `THREADS` | `4` | Worker threads. Must be `1` in MEM mode |
| `DEV_RELOAD` | `false` | Auto-reload on code changes |
| `PID_FILE` | `doorman.pid` | Process ID file path |

## Frontend Configuration

The web client is **domain-agnostic** and automatically detects the correct API URL at runtime:

- **Development (port 3000):** API calls → `http://localhost:3001`
- **Production/Reverse Proxy:** API calls → same origin as web client

**No configuration needed for reverse proxy deployments!** The frontend will automatically use the correct domain.

**Advanced Override (optional):**

If you need to manually override the API URL (e.g., separate API subdomain), you can set it in browser localStorage:

```javascript
localStorage.setItem('API_URL', 'https://api.doorman.example.com')
```

## Admin Credentials (Required)

| Variable | Description |
|----------|-------------|
| `DOORMAN_ADMIN_EMAIL` | Admin email (auto-created in MEM mode) |
| `DOORMAN_ADMIN_PASSWORD` | Admin password (min 12 chars) |

## Cache & Database

| Variable | Default | Description |
|----------|---------|-------------|
| `MEM_OR_EXTERNAL` | `MEM` | `MEM` (in-memory) or `REDIS` (production) |
| `MEM_ENCRYPTION_KEY` | - | 32+ char secret for memory dumps (required for dumps) |
| `MEM_DUMP_PATH` | `generated/memory_dump.bin` | Memory dump file path |
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database number |
| `MONGO_DB_HOSTS` | `localhost:27017` | MongoDB hosts (comma-separated) |
| `MONGO_REPLICA_SET_NAME` | `rs0` | MongoDB replica set name |

**Note:** `THREADS=1` required when `MEM_OR_EXTERNAL=MEM`

## Security & Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | - | **Required.** JWT signing secret (32+ chars) |
| `AUTH_EXPIRE_TIME` | `30` | Access token expiration (numeric) |
| `AUTH_EXPIRE_TIME_FREQ` | `minutes` | `seconds`, `minutes`, `hours`, `days` |
| `AUTH_REFRESH_EXPIRE_TIME` | `7` | Refresh token expiration (numeric) |
| `AUTH_REFRESH_EXPIRE_FREQ` | `days` | `seconds`, `minutes`, `hours`, `days` |
| `TOKEN_ENCRYPTION_KEY` | - | Encrypt API keys at rest (recommended) |
| `HTTPS_ONLY` | `false` | **Required in production.** Enforces HTTPS, secure cookies, CSRF |

## IP Access Control

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCAL_HOST_IP_BYPASS` | `false` | Localhost bypasses IP filters. **Disable in production** |

**Platform IP Settings** (configured via UI/API):
- `ip_whitelist` - Allowed IPs/CIDRs
- `ip_blacklist` - Denied IPs/CIDRs  
- `trust_x_forwarded_for` - Trust proxy headers
- `xff_trusted_proxies` - Trusted proxy IPs (required when trust=true)

## Request Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_BODY_SIZE_BYTES` | `1048576` (1MB) | Global max request body size |
| `MAX_BODY_SIZE_BYTES_REST` | - | Override for `/api/rest/*` |
| `MAX_BODY_SIZE_BYTES_SOAP` | - | Override for `/api/soap/*` (e.g., 2MB) |
| `MAX_BODY_SIZE_BYTES_GRAPHQL` | - | Override for `/api/graphql/*` |
| `MAX_BODY_SIZE_BYTES_GRPC` | - | Override for `/api/grpc/*` |
| `MAX_MULTIPART_SIZE_BYTES` | `10485760` (10MB) | Max multipart upload size |

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_FORMAT` | `plain` | `plain` or `json` (use json in production) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

## HTTP Resilience

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_CONNECT_TIMEOUT` | `5.0` | TCP connection timeout (seconds) |
| `HTTP_READ_TIMEOUT` | `30.0` | Response read timeout |
| `HTTP_WRITE_TIMEOUT` | `30.0` | Request write timeout |
| `HTTP_TIMEOUT` | `30.0` | Pool acquire timeout |
| `HTTP_RETRY_BASE_DELAY` | `0.25` | Retry base delay (seconds) |
| `HTTP_RETRY_MAX_DELAY` | `2.0` | Max retry backoff |
| `CIRCUIT_BREAKER_ENABLED` | `true` | Enable circuit breaker |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before opening |
| `CIRCUIT_BREAKER_TIMEOUT` | `30` | Seconds before half-open probe |

**Per-API overrides:** `api_connect_timeout`, `api_read_timeout`, `api_write_timeout`, `api_pool_timeout`, `api_allowed_retry_count`

## Other

| Variable | Default | Description |
|----------|---------|-------------|
| `STRICT_RESPONSE_ENVELOPE` | `false` | Wrap all platform API responses in envelope |

## Best Practices

**Development:**
- `MEM_OR_EXTERNAL=MEM`, `THREADS=1`
- `DEV_RELOAD=true`, `LOG_LEVEL=DEBUG`

**Production:**
- `ENV=production`, `HTTPS_ONLY=true` (required)
- `MEM_OR_EXTERNAL=REDIS`, `THREADS=4-8`
- `CORS_STRICT=true` with explicit origins
- `LOG_FORMAT=json`
- Store secrets in vault
- `LOCAL_HOST_IP_BYPASS=false`
