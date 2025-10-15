# Getting Started with Doorman

This guide walks you through installing and setting up Doorman API Gateway, from local development to your first API configuration.

## Prerequisites

- **Docker and Docker Compose** OR **Python 3.11+ and Node 20+**
- A domain you control (for production)
- TLS certificate and key (self-signed for dev, real cert for production)
- Optional: Redis and MongoDB (recommended for production)

## Quick Local Start (Development)

Local development uses convenient defaults that are **not secure for production**.

### 1. Clone and Start Services

```bash
# Clone the repository
git clone https://github.com/apidoorman/doorman.git
cd doorman

# Start with Docker Compose
docker compose up --build
```

**Services will be available at:**
- Backend API: `http://localhost:5001`
- Web UI: `http://localhost:3000`

### 2. Configure Environment Variables

Create a `.env` file in the `backend-services/` directory:

```bash
# Admin credentials (REQUIRED - change these!)
DOORMAN_ADMIN_EMAIL=admin@example.com
DOORMAN_ADMIN_PASSWORD=YourStrongPassword123!

# Cache/database mode
MEM_OR_EXTERNAL=MEM  # Use MEM for development, REDIS for production

# Memory encryption key (required for dumps)
MEM_ENCRYPTION_KEY=your-32-char-secret-for-encryption-here

# MongoDB configuration (optional in memory mode)
MONGO_DB_HOSTS=localhost:27017
MONGO_REPLICA_SET_NAME=rs0

# Redis configuration (when using MEM_OR_EXTERNAL=REDIS)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Memory dump path (memory mode only)
MEM_DUMP_PATH=backend-services/generated/memory_dump.bin

# JWT secrets (REQUIRED - change these!)
JWT_SECRET_KEY=change-this-to-a-strong-secret-key
TOKEN_ENCRYPTION_KEY=optional-secret-for-api-key-encryption

# HTTP/CORS configuration
ALLOWED_ORIGINS=http://localhost:3000
ALLOW_CREDENTIALS=True
ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD
ALLOW_HEADERS=*
HTTPS_ONLY=False  # Set to True in production
COOKIE_DOMAIN=localhost

# Application settings
PORT=5001
THREADS=4
DEV_RELOAD=False
SSL_CERTFILE=./certs/localhost.crt
SSL_KEYFILE=./certs/localhost.key
PID_FILE=doorman.pid
```

### 3. Create Required Directories

```bash
cd backend-services
mkdir -p proto generated certs
chmod 755 proto generated
```

### 4. Start Backend Service

**Option A: Background process**
```bash
cd backend-services
python doorman.py start
```

**Option B: Console mode (for debugging)**
```bash
cd backend-services
python doorman.py run
```

**Stop the background process:**
```bash
python doorman.py stop
```

### 5. Start Web Client

```bash
cd web-client
cp .env.local.example .env.local

# Edit .env.local and set:
# NEXT_PUBLIC_SERVER_URL=http://localhost:5001

npm ci
npm run dev  # Development mode
# OR
npm run build && npm start  # Production build
```

## First Login

### Via cURL

```bash
# Set your credentials
export DOORMAN_ADMIN_EMAIL="admin@example.com"
export DOORMAN_ADMIN_PASSWORD="YourStrongPassword123!"

# Login and save cookies
curl -s -c /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$DOORMAN_ADMIN_EMAIL\",\"password\":\"$DOORMAN_ADMIN_PASSWORD\"}" \
  http://localhost:5001/platform/authorization

# Check authentication status
curl -s -b /tmp/doorman.cookies \
  http://localhost:5001/platform/authorization/status
```

### Via Web UI

1. Navigate to `http://localhost:3000`
2. Login with your admin credentials
3. You'll be redirected to the dashboard

## Your First API

Let's publish a simple REST API backed by httpbin for testing.

### 1. Create a Token Group (for API key injection)

```bash
curl -s -b /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:5001/platform/credit \
  -d '{
    "api_credit_group": "demo-api",
    "api_key": "demo-secret-key-123",
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

### 2. Create the API

```bash
curl -s -b /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:5001/platform/api \
  -d '{
    "api_name": "demo",
    "api_version": "v1",
    "api_description": "Demo API for testing",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["ALL"],
    "api_servers": ["http://httpbin.org"],
    "api_type": "REST",
    "api_allowed_retry_count": 0,
    "api_allowed_headers": ["content-type", "accept"],
    "api_credits_enabled": true,
    "api_credit_group": "demo-api"
  }'
```

### 3. Add Endpoints

```bash
# GET endpoint
curl -s -b /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:5001/platform/endpoint \
  -d '{
    "api_name": "demo",
    "api_version": "v1",
    "endpoint_method": "GET",
    "endpoint_uri": "/get",
    "endpoint_description": "Echo GET request"
  }'

# POST endpoint
curl -s -b /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:5001/platform/endpoint \
  -d '{
    "api_name": "demo",
    "api_version": "v1",
    "endpoint_method": "POST",
    "endpoint_uri": "/post",
    "endpoint_description": "Echo POST request"
  }'
```

### 4. Subscribe Your User

```bash
curl -s -b /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:5001/platform/subscription/subscribe \
  -d '{
    "username": "admin",
    "api_name": "demo",
    "api_version": "v1"
  }'
```

### 5. Test Your API

```bash
# GET request
curl -s -b /tmp/doorman.cookies \
  "http://localhost:5001/api/rest/demo/v1/get?test=123"

# POST request
curl -s -b /tmp/doorman.cookies \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello Doorman!"}' \
  http://localhost:5001/api/rest/demo/v1/post
```

Doorman will automatically inject the `x-api-key` header to the upstream service!

## Alternative: Manual Installation (Without Docker)

### Backend Setup

```bash
cd backend-services
pip install -r requirements.txt

# Create directories
mkdir -p proto generated certs

# Configure .env (see step 2 above)

# Start the service
python doorman.py start
```

### Frontend Setup

```bash
cd web-client
npm ci
cp .env.local.example .env.local

# Edit .env.local and configure NEXT_PUBLIC_SERVER_URL

npm run dev
```

## Generate Self-Signed Certificate (Development)

```bash
cd backend-services/certs

openssl req -x509 -newkey rsa:4096 -sha256 -days 365 -nodes \
  -keyout localhost.key -out localhost.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

## User Custom Attributes Limit

Each user can have a maximum of **10 custom attribute key/value pairs**:

- API requests exceeding this limit return **HTTP 400** with error code `USR016`
- UI prevents adding more than 10 attributes with a helper message
- Use short, stable keys like `dept`, `tier`, `region` to stay within limits

## Next Steps

- **Production Setup**: See [Getting Started - Secure Production](./01-getting-started.md#secure-production-setup) below
- **Configuration**: Review the [Configuration Reference](./02-configuration.md)
- **Security**: Read the [Security Guide](./03-security.md) for hardening
- **Workflows**: Explore [API Workflows](./04-api-workflows.md) for real-world examples

---

## Secure Production Setup

Production requires explicit, strong secrets and HTTPS enforcement. Doorman **refuses to start** if `ENV=production` and neither `HTTPS_ONLY` nor `HTTPS_ENABLED` are true.

### 1. Required Production Secrets

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

# JWT and encryption (REQUIRED - use strong random values!)
JWT_SECRET_KEY=use-a-strong-random-secret-at-least-32-chars
TOKEN_ENCRYPTION_KEY=another-strong-secret-for-api-key-encryption
MEM_ENCRYPTION_KEY=yet-another-strong-secret-for-memory-dumps

# CORS (restrict origins, no wildcards)
ALLOWED_ORIGINS=https://admin.yourdomain.com,https://api.yourdomain.com
CORS_STRICT=true
COOKIE_DOMAIN=yourdomain.com
ALLOW_CREDENTIALS=True

# Cache and Database
MEM_OR_EXTERNAL=REDIS    # Use Redis in production
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
MONGO_DB_HOSTS=mongo:27017
MONGO_REPLICA_SET_NAME=rs0

# Logging
LOG_FORMAT=json          # Structured logs for SIEM ingestion

# Request limits
MAX_BODY_SIZE_BYTES=1048576  # 1MB default
```

### 2. Production Docker Compose Example

```yaml
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
      REDIS_PORT: 6379
      MONGO_DB_HOSTS: mongo:27017
      MONGO_REPLICA_SET_NAME: rs0
    volumes:
      - ./certs:/certs:ro
    depends_on:
      - redis
      - mongo
    ports:
      - "5001:5001"

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  mongo:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
    volumes:
      - mongo-data:/data/db

volumes:
  redis-data:
  mongo-data:
```

### 3. TLS Certificate Options

**Option A: Doorman terminates TLS**
- Mount certificates into container
- Set `HTTPS_ONLY=true`
- Configure `SSL_CERTFILE` and `SSL_KEYFILE`

**Option B: Reverse proxy terminates TLS**
- Run backend over HTTP
- Set `HTTPS_ENABLED=true`
- Ensure proxy forwards `X-Forwarded-Proto: https`
- Only expose HTTPS to clients

### 4. Production Hardening Checklist

- [ ] Set `ENV=production`
- [ ] Enable `HTTPS_ONLY=true` or `HTTPS_ENABLED=true`
- [ ] Use real TLS certificates (not self-signed)
- [ ] Change all default secrets (`JWT_SECRET_KEY`, etc.)
- [ ] Set `CORS_STRICT=true` with explicit `ALLOWED_ORIGINS`
- [ ] Configure `COOKIE_DOMAIN` to match your domain
- [ ] Use `LOG_FORMAT=json` for structured logging
- [ ] Enable Redis for distributed rate limiting
- [ ] Enable MongoDB for persistence
- [ ] Remove default admin password immediately after first login
- [ ] Configure IP whitelisting if needed
- [ ] Set `MAX_BODY_SIZE_BYTES` appropriate for your use case
- [ ] Run containers as non-root (already configured in Dockerfile)
- [ ] Place backend on private network
- [ ] Only expose reverse proxy to public internet

### 5. First Production Login

```bash
# Login with your production admin credentials
BASE=https://api.yourdomain.com
COOKIE=/tmp/doorman-prod.cookies

curl -s -c "$COOKIE" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@yourdomain.com","password":"<strong-password>"}' \
  "$BASE/platform/authorization"

# Immediately change the admin password via the UI
# Create least-privilege users for day-to-day operations
```

### 6. IP Access Control (Production)

If running behind a reverse proxy or load balancer, configure IP trust settings:

```bash
# Platform-wide IP settings (via UI or API)
{
  "ip_whitelist": ["10.0.0.0/8", "192.168.1.0/24"],  # Optional
  "ip_blacklist": ["1.2.3.4"],                        # Optional
  "trust_x_forwarded_for": true,                      # Trust proxy headers
  "xff_trusted_proxies": ["10.0.1.10", "10.0.1.11"]   # REQUIRED when trust=true
}
```

**Important:** Set `LOCAL_HOST_IP_BYPASS=false` in production to prevent localhost bypass.

### 7. Monitoring and Health Checks

Configure your load balancer to use these endpoints:

```bash
# Liveness probe (basic health)
GET https://api.yourdomain.com/platform/monitor/liveness

# Readiness probe (checks Redis/MongoDB)
GET https://api.yourdomain.com/platform/monitor/readiness

# Metrics (requires authentication + manage_gateway permission)
GET https://api.yourdomain.com/platform/monitor/metrics?range=24h
```

## Troubleshooting

### Server Won't Start

**Error:** "HTTPS is required in production"
- Set `HTTPS_ONLY=true` or `HTTPS_ENABLED=true`

**Error:** "JWT_SECRET_KEY not set"
- Configure `JWT_SECRET_KEY` in `.env`

### Cannot Login

**401 Unauthorized**
- Verify admin email/password in `.env`
- Check that admin user was created (memory mode auto-creates on startup)

### CORS Errors

**Preflight request fails**
- Add your origin to `ALLOWED_ORIGINS`
- Set `ALLOW_CREDENTIALS=True` if using cookies
- Ensure `CORS_STRICT=true` in production

### API Gateway Returns 404

**GTW001: API not found**
- Verify `api_name` and `api_version` are correct
- Check API was created successfully

**GTW003: Endpoint not found**
- Verify endpoint method and URI match exactly
- Check endpoint was added to the API

## Need Help?

- [Configuration Reference](./02-configuration.md) - All environment variables
- [Security Guide](./03-security.md) - Hardening and best practices
- [API Workflows](./04-api-workflows.md) - Real-world examples
- [Operations Guide](./05-operations.md) - Production runbooks
