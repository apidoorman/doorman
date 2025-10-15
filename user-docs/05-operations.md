# Operations Guide

Production deployment, monitoring, and operational runbooks for Doorman API Gateway.

## Overview

This guide covers:
- Production environment configuration
- Deployment strategies
- Health checks and monitoring
- Redis and MongoDB setup
- Operational runbooks
- Graceful restarts and memory management
- Response envelope configuration

---

## Production Environment Configuration

### Required Production Settings

```bash
# Environment
ENV=production

# HTTPS (REQUIRED - at least one must be true)
HTTPS_ONLY=true          # Doorman terminates TLS
# OR
HTTPS_ENABLED=true       # TLS terminated at reverse proxy

# SSL certificates (if HTTPS_ONLY=true)
SSL_CERTFILE=/certs/fullchain.pem
SSL_KEYFILE=/certs/privkey.pem

# Secrets (REQUIRED - use strong random values)
JWT_SECRET_KEY=<strong-random-secret-32chars+>
TOKEN_ENCRYPTION_KEY=<api-key-encryption-secret-32chars+>
MEM_ENCRYPTION_KEY=<memory-dump-encryption-secret-32chars+>

# CORS (strict configuration)
ALLOWED_ORIGINS=https://admin.yourdomain.com,https://api.yourdomain.com
CORS_STRICT=true
COOKIE_DOMAIN=yourdomain.com
ALLOW_CREDENTIALS=True

# Cache and Database
MEM_OR_EXTERNAL=REDIS    # Use Redis in production
REDIS_HOST=redis.internal
REDIS_PORT=6379
REDIS_DB=0

MONGO_DB_HOSTS=mongo1.internal:27017,mongo2.internal:27017,mongo3.internal:27017
MONGO_REPLICA_SET_NAME=rs0

# Logging
LOG_FORMAT=json          # Structured logs for SIEM
LOG_LEVEL=INFO

# Request limits
MAX_BODY_SIZE_BYTES=1048576        # 1MB default
MAX_BODY_SIZE_BYTES_SOAP=2097152   # 2MB for SOAP

# Response envelopes
STRICT_RESPONSE_ENVELOPE=true      # Consistent API responses

# Security
LOCAL_HOST_IP_BYPASS=false         # Disable localhost bypass
```

### Recommended Defaults

| Setting | Value | Purpose |
|---------|-------|---------|
| `HTTPS_ONLY` | `true` | Set `Secure` flag on cookies |
| `HTTPS_ENABLED` | `true` | Enforce CSRF double-submit |
| `CORS_STRICT` | `true` | Disallow wildcard origins with credentials |
| `LOG_FORMAT` | `json` | JSON log output for log pipelines |
| `MAX_BODY_SIZE_BYTES` | `1048576` | Reject requests above 1MB |
| `STRICT_RESPONSE_ENVELOPE` | `true` | Consistent platform API responses |

### JWT and Token Configuration

```bash
# JWT secret (REQUIRED - gateway fails fast if missing)
JWT_SECRET_KEY=<strong-secret-store-in-vault>

# Access token lifetime (default: 30 minutes)
AUTH_EXPIRE_TIME=30
AUTH_EXPIRE_TIME_FREQ=minutes

# Refresh token lifetime (default: 7 days)
AUTH_REFRESH_EXPIRE_TIME=7
AUTH_REFRESH_EXPIRE_FREQ=days

# API key encryption at rest (recommended)
TOKEN_ENCRYPTION_KEY=<encryption-key-32chars+>
```

**Best practices:**
- Store secrets in a secret manager (Vault, AWS Secrets Manager, etc.)
- Rotate `JWT_SECRET_KEY` every 90 days
- Rotate encryption keys every 180 days
- Never commit secrets to version control

---

## Deployment

### Single-Instance Deployment

**Docker Compose:**

```yaml
version: '3.8'

services:
  backend:
    build: ./backend-services
    environment:
      ENV: production
      HTTPS_ONLY: "true"
      SSL_CERTFILE: /certs/fullchain.pem
      SSL_KEYFILE: /certs/privkey.pem
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      TOKEN_ENCRYPTION_KEY: ${TOKEN_ENCRYPTION_KEY}
      MEM_ENCRYPTION_KEY: ${MEM_ENCRYPTION_KEY}
      ALLOWED_ORIGINS: https://admin.yourdomain.com
      CORS_STRICT: "true"
      COOKIE_DOMAIN: yourdomain.com
      LOG_FORMAT: json
      MEM_OR_EXTERNAL: REDIS
      REDIS_HOST: redis
      MONGO_DB_HOSTS: mongo:27017
      MONGO_REPLICA_SET_NAME: rs0
    volumes:
      - ./certs:/certs:ro
      - ./logs:/app/logs
    ports:
      - "5001:5001"
    depends_on:
      - redis
      - mongo
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    restart: unless-stopped

  mongo:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    volumes:
      - mongo-data:/data/db
    restart: unless-stopped

volumes:
  redis-data:
  mongo-data:
```

### Multi-Instance Deployment

**Important:** Memory mode (`MEM_OR_EXTERNAL=MEM`) requires a single worker. For multiple instances or `THREADS>1`, use Redis mode. Startup includes a guard that fails fast when `MEM_OR_EXTERNAL=MEM` and `THREADS>1` to prevent unsafe token revocation and rate limiting semantics across workers.

**Requirements:**
- Redis for shared cache and rate limiting
- MongoDB for persistence
- Load balancer with sticky sessions (for cookie-based auth)

**Example with multiple replicas:**

```yaml
services:
  backend:
    # ... same config as above ...
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
    environment:
      THREADS: 4  # Workers per instance
      # ... other config ...
```

### Reverse Proxy Deployment

**Nginx example:**

```nginx
upstream doorman_backend {
    server 127.0.0.1:5001;
    # Or multiple instances:
    # server backend1:5001;
    # server backend2:5001;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://doorman_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

**Doorman configuration for proxy:**

```bash
# Backend listens on HTTP but enforces secure behavior
HTTPS_ENABLED=true  # NOT HTTPS_ONLY
PORT=5001

# Trust proxy headers
trust_x_forwarded_for=true
xff_trusted_proxies=["10.0.1.10"]  # Nginx IP
```

---

## Redis Setup

### Standalone Redis

```bash
# Docker
docker run -d --name redis \
  -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine redis-server --appendonly yes

# Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Redis Sentinel (High Availability)

```yaml
# docker-compose.yml
services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-master-data:/data

  redis-sentinel:
    image: redis:7-alpine
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./sentinel.conf:/etc/redis/sentinel.conf:ro
    depends_on:
      - redis-master
```

### Redis Cluster

For large-scale deployments:

```bash
# Use Redis Cluster for horizontal scaling
REDIS_HOST=redis-cluster-node1:6379,redis-cluster-node2:6379,redis-cluster-node3:6379
```

---

## MongoDB Setup

### Replica Set (Recommended)

**Initialize replica set:**

```bash
# Start MongoDB
docker run -d --name mongo \
  -p 27017:27017 \
  mongo:7 --replSet rs0 --bind_ip_all

# Initialize replica set
docker exec -it mongo mongosh --eval "rs.initiate({
  _id: 'rs0',
  members: [
    { _id: 0, host: 'mongo:27017' }
  ]
})"

# Verify status
docker exec -it mongo mongosh --eval "rs.status()"
```

**Configuration:**

```bash
MONGO_DB_HOSTS=mongo:27017
MONGO_REPLICA_SET_NAME=rs0
```

### Multi-Node Replica Set (Production)

```yaml
# docker-compose.yml
services:
  mongo1:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    volumes:
      - mongo1-data:/data/db

  mongo2:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    volumes:
      - mongo2-data:/data/db

  mongo3:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    volumes:
      - mongo3-data:/data/db
```

**Initialize:**

```bash
docker exec -it mongo1 mongosh --eval "rs.initiate({
  _id: 'rs0',
  members: [
    { _id: 0, host: 'mongo1:27017' },
    { _id: 1, host: 'mongo2:27017' },
    { _id: 2, host: 'mongo3:27017' }
  ]
})"
```

**Configuration:**

```bash
MONGO_DB_HOSTS=mongo1:27017,mongo2:27017,mongo3:27017
MONGO_REPLICA_SET_NAME=rs0
```

---

## Health Checks and Monitoring

### Health Endpoints

**Liveness Probe** - Basic health check:
```bash
GET /platform/monitor/liveness

# Response:
{"status": "alive"}
```

**Readiness Probe** - Checks dependencies:
```bash
GET /platform/monitor/readiness

# Response:
{
  "status": "ready",
  "mongodb": "connected",
  "redis": "connected"
}
```

**Gateway Status** (public):
```bash
GET /api/health  # public probe

GET /api/status  # detailed (requires manage_gateway)

# Response:
{
  "status": "ok",
  "uptime_seconds": 12345,
  "memory_usage_mb": 256,
  "mode": "redis"
}
```

### Kubernetes Probes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: doorman-backend
spec:
  containers:
  - name: backend
    image: doorman:latest
    livenessProbe:
      httpGet:
        path: /platform/monitor/liveness
        port: 5001
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /platform/monitor/readiness
        port: 5001
      initialDelaySeconds: 5
      periodSeconds: 10
```

### Metrics Endpoint

**Requires authentication + `manage_gateway` permission:**

```bash
GET /platform/monitor/metrics?range=24h

# Response:
{
  "period": "24h",
  "total_requests": 125000,
  "total_errors": 250,
  "error_rate": 0.002,
  "avg_response_time_ms": 45,
  "p50_response_time_ms": 35,
  "p95_response_time_ms": 120,
  "p99_response_time_ms": 250,
  "apis": {
    "customers/v1": {
      "requests": 50000,
      "errors": 100,
      "avg_response_time_ms": 40
    }
  }
}
```

**Prometheus integration:**

Export metrics to Prometheus for alerting and dashboards:

```python
# Add Prometheus exporter middleware (future enhancement)
# Metrics: request_count, request_duration, error_count, credit_usage
```

---

## Logging

### Log Files

- **Main log:** `backend-services/logs/doorman.log`
- **Audit trail:** `backend-services/logs/doorman-trail.log`

### Log Formats

**Plain text (development):**
```
2024-01-15 10:30:00 INFO [request_id=abc123] User admin logged in
```

**JSON (production):**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "request_id": "abc123",
  "message": "User admin logged in",
  "username": "admin",
  "client_ip": "192.168.1.100"
}
```

**Configuration:**
```bash
LOG_FORMAT=json
LOG_LEVEL=INFO
```

### Log Shipping

**Fluentd example:**

```yaml
# fluentd.conf
<source>
  @type tail
  path /app/logs/doorman*.log
  pos_file /var/log/td-agent/doorman.pos
  tag doorman.*
  <parse>
    @type json
    time_key timestamp
    time_format %Y-%m-%dT%H:%M:%SZ
  </parse>
</source>

<match doorman.**>
  @type elasticsearch
  host elasticsearch.internal
  port 9200
  index_name doorman
  type_name _doc
</match>
```

---

## Memory Management

### Memory Mode

**When to use:**
- Development and testing
- Single-instance deployments
- Small workloads

**Configuration:**
```bash
MEM_OR_EXTERNAL=MEM
MEM_ENCRYPTION_KEY=<32-char-secret>
MEM_DUMP_PATH=backend-services/generated/memory_dump.bin
THREADS=1  # REQUIRED - only 1 worker in memory mode
```

**Memory dumps:**
- Written on graceful shutdown
- Can be triggered manually via `/platform/security/settings`
- Encrypted with `MEM_ENCRYPTION_KEY`
- Restored automatically on startup

**Manual dump trigger:**
```bash
PUT /platform/security/settings
{
  "auto_save_memory_enabled": true,
  "auto_save_memory_interval_minutes": 30
}
```

### Redis Mode

**When to use:**
- Production deployments
- Multi-instance setups
- High traffic workloads

**Configuration:**
```bash
MEM_OR_EXTERNAL=REDIS
REDIS_HOST=redis.internal
REDIS_PORT=6379
REDIS_DB=0
THREADS=4  # Can use multiple workers
```

**Benefits:**
- Distributed rate limiting
- Shared cache across instances
- No state divergence between workers

---

## Operational Runbooks

### Runbook 1: Graceful Restart

**Goal:** Restart gateway with zero downtime.

**Steps:**

1. **Verify health:**
   ```bash
   curl https://api.yourdomain.com/platform/monitor/readiness
   ```

2. **Trigger memory dump (if memory mode):**
   ```bash
   python doorman.py stop  # Writes dump automatically
   ```

3. **Restart service:**
   ```bash
   # Docker Compose
   docker compose restart backend

   # Systemd
   sudo systemctl restart doorman

   # Direct
   python doorman.py start
   ```

4. **Verify startup:**
   ```bash
   tail -f logs/doorman.log
   # Look for: "Application startup complete"
   ```

5. **Check health:**
   ```bash
   curl https://api.yourdomain.com/platform/monitor/readiness
   ```

### Runbook 2: Token Compromise Response

**Goal:** Revoke compromised tokens and secure system.

**Steps:**

1. **Identify affected user:**
   ```bash
   grep "suspicious-activity" logs/doorman-trail.log
   ```

2. **Revoke user's tokens:**
   ```bash
   POST /platform/authorization/invalidate
   {"username": "affected-user"}
   ```

3. **Force password reset:**
   ```bash
   PUT /platform/user/affected-user
   {"force_password_reset": true}
   ```

4. **Audit recent activity:**
   ```bash
   grep "affected-user" logs/doorman-trail.log | tail -100
   ```

5. **If widespread compromise, rotate JWT secret:**
   ```bash
   # Update .env with new JWT_SECRET_KEY
   # Restart gateway (invalidates all tokens)
   docker compose restart backend
   ```

### Runbook 3: Elevated Error Rates

**Goal:** Diagnose and resolve high error rates.

**Steps:**

1. **Check health endpoints:**
   ```bash
   curl https://api.yourdomain.com/platform/monitor/readiness
   ```

2. **Review recent errors:**
   ```bash
   tail -100 logs/doorman.log | grep ERROR
   ```

3. **Check Redis connectivity:**
   ```bash
   redis-cli -h redis.internal ping
   ```

4. **Check MongoDB connectivity:**
   ```bash
   mongosh --host mongo.internal --eval "db.adminCommand('ping')"
   ```

5. **Review metrics:**
   ```bash
   curl -b cookies.txt https://api.yourdomain.com/platform/monitor/metrics?range=1h
   ```

6. **Common fixes:**
   - Restart Redis if connection errors
   - Restart MongoDB if replica set issues
   - Scale up instances if overloaded
   - Check upstream service health

### Runbook 4: CORS Configuration Issues

**Goal:** Fix CORS preflight failures.

**Steps:**

1. **Use CORS checker:**
   ```bash
   POST /platform/tools/cors/check
   {
     "origin": "https://app.example.com",
     "method": "POST",
     "request_headers": ["Content-Type", "Authorization"],
     "with_credentials": true
   }
   ```

2. **Review effective config:**
   ```bash
   # Check environment variables
   echo $ALLOWED_ORIGINS
   echo $CORS_STRICT
   ```

3. **Common fixes:**
   - Add origin to `ALLOWED_ORIGINS`
   - Set `CORS_STRICT=true` to reject wildcard with credentials
   - Ensure `ALLOW_CREDENTIALS=true` if using cookies
   - Verify `COOKIE_DOMAIN` matches origin hostname

4. **Restart to apply changes:**
   ```bash
   docker compose restart backend
   ```

### Runbook 5: CSRF Validation Failures

**Goal:** Fix CSRF token errors.

**Steps:**

1. **Verify HTTPS config:**
   ```bash
   echo $HTTPS_ONLY
   echo $HTTPS_ENABLED
   # At least one must be true for CSRF
   ```

2. **Check client implementation:**
   - Ensure client reads `csrf_token` cookie
   - Verify `X-CSRF-Token` header is sent
   - Confirm header value matches cookie

3. **Test with curl:**
   ```bash
   # Login and get CSRF token
   curl -c cookies.txt -s \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin@example.com","password":"..."}' \
     https://api.example.com/platform/authorization

   # Extract CSRF token
   CSRF_TOKEN=$(grep csrf_token cookies.txt | awk '{print $7}')

   # Use in request
   curl -b cookies.txt \
     -H "X-CSRF-Token: $CSRF_TOKEN" \
     -H 'Content-Type: application/json' \
     -X POST https://api.example.com/platform/api -d '{...}'
   ```

4. **Common fixes:**
   - Enable HTTPS if not already
   - Ensure `COOKIE_DOMAIN` is correct
   - Check that cookies are not blocked by browser

---

## Response Envelope Configuration

### Strict Response Envelope

When `STRICT_RESPONSE_ENVELOPE=true`, platform endpoints return consistent structure:

**Success (200):**
```json
{
  "status_code": 200,
  "response": {
    "api_name": "customers",
    "api_version": "v1"
  }
}
```

**Created (201):**
```json
{
  "status_code": 201,
  "message": "Resource created successfully"
}
```

**Error (400/403/404):**
```json
{
  "status_code": 403,
  "error_code": "ROLE009",
  "error_message": "You do not have permission to create roles"
}
```

**Gateway responses (`/api/*`):**
- Not wrapped by default
- Return upstream response as-is
- Can be enabled per-API if needed

**When to enable:**
- Client expects consistent envelope
- Standardized error handling
- API versioning and evolution

**When to disable:**
- Clients expect raw upstream responses

---

## SLI Dashboard and Alerts (Prometheus/Grafana)

Starter assets are included:

- `ops/grafana-dashboard.json` — Grafana dashboard panels for:
  - p95 latency (ms)
  - Error rate
  - Upstream timeout rate
  - Retry rate

- `ops/alerts-prometheus.yml` — Prometheus alert rules:
  - High p95 latency (> 250ms for 10m)
  - High error rate (> 1% for 10m)
  - Upstream timeout spike
  - Elevated retry rate

Import and tune thresholds to match your SLOs.

## Load Testing with k6

Use `load-tests/k6/load.test.js` to validate performance and SLOs in CI:

```bash
k6 run load-tests/k6/load.test.js \
  -e BASE_URL=http://localhost:3001 \
  -e RPS=50 \
  -e DURATION=2m \
  -e REST_PATHS='["/api/rest/health"]' \
  -e PLATFORM_PATHS='["/platform/authorization/status"]'
```

Thresholds embedded in the script will fail the run if unmet. A JUnit report (`junit.xml`) is emitted for CI.

## Logging Redaction

Redaction is applied at the logger/filter layer, so sensitive data such as Authorization headers (Bearer/Basic), `X-API-Key`, Set‑Cookie/Cookie values, JWT‑like strings, and common secret fields are masked before logs are written or shipped.

## Pagination Defaults and Caps

Server‑side pagination is enforced across list endpoints.

```bash
# Maximum page size (default 100 if unset)
MAX_PAGE_SIZE=100

# Clients should pass page & page_size explicitly, e.g., /platform/role/all?page=1&page_size=50
```

- Maximum compatibility
- Minimal overhead

---

## Backup and Disaster Recovery

### Database Backups

**MongoDB:**
```bash
# Dump to file
mongodump --host mongo.internal --out /backups/$(date +%Y%m%d)

# Restore from file
mongorestore --host mongo.internal /backups/20240115
```

**Redis:**
```bash
# Manual save
redis-cli -h redis.internal SAVE

# Automated snapshots (redis.conf)
save 900 1      # After 900 sec if 1 key changed
save 300 10     # After 300 sec if 10 keys changed
save 60 10000   # After 60 sec if 10000 keys changed
```

### Memory Dumps

**Manual trigger:**
```bash
# Via API
PUT /platform/security/settings
{
  "auto_save_memory_enabled": true,
  "auto_save_memory_interval_minutes": 30
}
```

**Automatic on shutdown:**
- Graceful stop writes encrypted dump
- Location: `$MEM_DUMP_PATH-YYYYMMDDTHHMMSSZ.bin`

**Restore:**
- Place latest dump in `backend-services/generated/` directory
- Rename to match `MEM_DUMP_PATH` without timestamp
- Start gateway (auto-loads dump)

---

## Performance Tuning

### Worker Threads

```bash
# Default: 4 workers
THREADS=4

# Memory mode: MUST be 1
THREADS=1

# High traffic: 8-16 workers
THREADS=8
```

### Connection Pooling

Upstream connections are pooled automatically. No configuration needed.

### Request Limits

```bash
# Balance security and usability
MAX_BODY_SIZE_BYTES=1048576         # 1MB for most APIs
MAX_BODY_SIZE_BYTES_SOAP=2097152    # 2MB for large SOAP envelopes
MAX_MULTIPART_SIZE_BYTES=10485760   # 10MB for file uploads
```

### Caching

**Redis caching:**
- Rate limit state
- Token blacklist
- Session data

**TTLs:**
- Access tokens: 30 minutes (configurable)
- Refresh tokens: 7 days (configurable)
- Rate limit windows: 1 minute to 1 day

---

## Production Checklist

Before going live:

- [ ] `ENV=production` set
- [ ] HTTPS enabled (`HTTPS_ONLY` or `HTTPS_ENABLED`)
- [ ] Valid TLS certificates configured
- [ ] Strong `JWT_SECRET_KEY` set
- [ ] `TOKEN_ENCRYPTION_KEY` and `MEM_ENCRYPTION_KEY` configured
- [ ] `ALLOWED_ORIGINS` set to explicit domains
- [ ] `CORS_STRICT=true`
- [ ] `COOKIE_DOMAIN` matches your domain
- [ ] Redis configured and tested
- [ ] MongoDB replica set configured
- [ ] `LOG_FORMAT=json` enabled
- [ ] Log shipping to SIEM configured
- [ ] Health checks configured in load balancer
- [ ] Metrics monitoring set up
- [ ] Backup strategy defined
- [ ] Runbooks documented for your team
- [ ] Admin password rotated
- [ ] Least-privilege users created
- [ ] IP whitelisting configured (if needed)
- [ ] Rate limits tested
- [ ] Load testing completed

---

## Support and Troubleshooting

**Documentation:**
- [Configuration Reference](./02-configuration.md)
- [Security Guide](./03-security.md)
- [API Workflows](./04-api-workflows.md)
- [Tools](./06-tools.md)

**Logs to check:**
- `logs/doorman.log` - Application log
- `logs/doorman-trail.log` - Audit trail

**Common issues:**
- Review the [API Workflows - Troubleshooting](./04-api-workflows.md#common-errors-and-troubleshooting) section
- Use the CORS checker tool for CORS issues
- Check health endpoints for dependency problems
### Request ID Propagation

- Every request carries a `X-Request-ID` for end‑to‑end tracing.
- Doorman forwards `X-Request-ID` to upstreams and echoes it back in responses.
- If an upstream echoes its own header (e.g., `X-Upstream-Request-ID`), add it to your API’s `api_allowed_headers` so the gateway exposes it back to clients.

### HTTP Resilience & Backoff

- Upstream calls use jittered exponential backoff and a simple circuit breaker.
- Tune via environment variables (see Configuration → HTTP Resilience).
- Use per‑API retry count (`api_allowed_retry_count`) to control retry behavior.
