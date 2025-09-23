# Doorman (pygate) — Secure Get Started Guide

This guide helps you stand up Doorman securely, from local dev to a minimal production deployment. It uses real-world examples and emphasizes safe defaults.

## Who This Is For
- Platform engineers/SREs deploying an API gateway
- Developers integrating REST/GraphQL/SOAP/gRPC backends

## Prerequisites
- Docker and Docker Compose OR Python 3.11 + Node 20
- A domain you control (prod)
- TLS certificate and key (self-signed for dev or a real cert in prod)
- Optional: Redis and MongoDB (recommended for prod)

## Repo Layout (relevant pieces)
- `backend-services/`: FastAPI gateway core (`doorman.py`)
- `web-client/`: Next.js admin UI
- `docker-compose.yml`: Two services (`backend`, `web`)

## Quick Local Start (development)
Local dev defaults are convenient but not secure; do not use them in production.

1) Start everything
   - `docker compose up --build`
   - Backend: `http://localhost:5001`
   - Web UI: `http://localhost:3000`

2) Login to the platform
   - Admin user is seeded when running in memory mode: `username=admin`, `email=$STARTUP_ADMIN_EMAIL`
   - Default compose envs (dev only):
     - `STARTUP_ADMIN_EMAIL=admin@localhost`
     - `STARTUP_ADMIN_PASSWORD=password1`

   cURL login and status check:
   - `curl -s -c /tmp/doorman.cookies -H 'Content-Type: application/json' -d '{"email":"admin@localhost","password":"password1"}' http://localhost:5001/platform/authorization`
   - `curl -s -b /tmp/doorman.cookies http://localhost:5001/platform/authorization/status`

3) Web UI setup
   - The UI builds with `NEXT_PUBLIC_SERVER_URL` pointing at the backend (compose sets it to `http://backend:5001`). If running outside compose for dev, set `web-client/.env.local` with `NEXT_PUBLIC_SERVER_URL=http://localhost:5001` and run:
     - `npm ci`
     - `npm run dev` (or `npm run build && npm start`)

## Secure Production Setup

Use explicit, strong secrets and force HTTPS. You can terminate TLS either at Doorman itself or at a reverse proxy (Nginx/Traefik). In production, Doorman refuses to start if `ENV=production` and neither `HTTPS_ONLY` nor `HTTPS_ENABLED` are true.

### 1) Required secrets and security env
- `JWT_SECRET_KEY`: REQUIRED. Long, random string for access tokens.
- `TOKEN_ENCRYPTION_KEY`: Encrypts API keys at rest.
- `MEM_ENCRYPTION_KEY`: Encrypts memory dump files when in memory mode.
- `ALLOWED_ORIGINS`: Exact origins allowed by CORS (no `*` with credentials).
- `CORS_STRICT=true`: Disallow wildcard origins when using credentials.
- `COOKIE_DOMAIN=yourdomain.com`: Must match your site host for secure cookies.
- `HTTPS_ONLY=true` OR `HTTPS_ENABLED=true` with `ENV=production`.
- `LOG_FORMAT=json`: Structured logs for ingestion.
- `MAX_BODY_SIZE_BYTES` (optional): Enforce upload size limits (default 1MB).

Example compose override (prod-only values):

```yaml
services:
  backend:
    environment:
      ENV: production
      PORT: 5001
      MEM_OR_EXTERNAL: REDIS
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      TOKEN_ENCRYPTION_KEY: ${TOKEN_ENCRYPTION_KEY}
      MEM_ENCRYPTION_KEY: ${MEM_ENCRYPTION_KEY}
      ALLOWED_ORIGINS: https://admin.yourdomain.com
      CORS_STRICT: "true"
      COOKIE_DOMAIN: yourdomain.com
      LOG_FORMAT: json
      HTTPS_ONLY: "true"          # or set HTTPS_ENABLED if TLS is at proxy
      SSL_CERTFILE: /certs/fullchain.pem
      SSL_KEYFILE: /certs/privkey.pem
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_DB: 0
      MONGO_DB_HOSTS: mongo:27017
      MONGO_REPLICA_SET_NAME: rs0
    volumes:
      - ./certs:/certs:ro
    depends_on:
      - redis
      - mongo

  redis:
    image: redis:7-alpine

  mongo:
    image: mongo:7
    command: --replSet rs0 --bind_ip_all
```

Notes
- Memory mode (`MEM_OR_EXTERNAL=MEM`) is fine for demos/single-node but uses in-memory DB. Prefer `REDIS` for distributed rate limiting and pair with MongoDB for persistence.
- If you terminate TLS at a reverse proxy, set `HTTPS_ENABLED=true` so Doorman emits Secure cookies and HSTS headers even though it listens on HTTP behind the proxy.

### 2) Certificates

Option A — Terminate TLS in Doorman
- Mount your certs into the container and set `HTTPS_ONLY=true`, `SSL_CERTFILE`, `SSL_KEYFILE`.

Option B — Terminate TLS at a reverse proxy
- Run the backend over HTTP, but set `HTTPS_ENABLED=true` and ensure the proxy only exposes HTTPS to clients. Forward `X-Forwarded-Proto: https` if applicable.

Dev self-signed example (OpenSSL):
```
openssl req -x509 -newkey rsa:4096 -sha256 -days 365 -nodes \
  -keyout ./certs/localhost.key -out ./certs/localhost.crt \
  -subj "/CN=localhost"
```

### 3) Database and cache
- Redis: Required in prod for distributed rate limiting; configure `REDIS_*` envs.
- MongoDB: Recommended for persistence; set `MONGO_DB_HOSTS` and `MONGO_REPLICA_SET_NAME` for HA.
- Memory dumps: In memory-mode, Doorman writes encrypted dumps to `MEM_DUMP_PATH`. Use `/platform/security/settings` to auto-save on an interval.

### 4) First admin login (prod)
- Use your real admin email/password via env.
- Login via UI or cURL, then immediately rotate the admin password and create least-privilege users.

### 5) Hardening checklist
- Set `ENV=production` and enable HTTPS (`HTTPS_ONLY` or `HTTPS_ENABLED`).
- Remove default dev passwords. Store secrets in your secret manager.
- Lock down CORS with `CORS_STRICT=true` and explicit `ALLOWED_ORIGINS`.
- Set `COOKIE_DOMAIN` to your domain.
- Prefer `LOG_FORMAT=json`. Forward logs to your SIEM.
- Limit request size: `MAX_BODY_SIZE_BYTES`.
- Run containers as non-root (Dockerfiles already do).
- Place the backend on a private network; only expose your reverse proxy.

## Real-World Example: Bring a REST API Online Securely

Assume you have an internal upstream at `http://orders-api.internal:8080` and you want to publish it at `/api/rest/orders/v1/*` with API-key injection and validation.

1) Login and capture cookies
```
BASE=http://your-backend:5001
COOKIE=/tmp/doorman.cookies
curl -s -c "$COOKIE" -H 'Content-Type: application/json' \
  -d '{"email":"admin@yourdomain.com","password":"<strong-password>"}' \
  "$BASE/platform/authorization"
```

2) Define a token group for the upstream’s API key
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit" -d '{
    "api_credit_group": "orders-upstream",
    "api_key": "REDACTED_REAL_KEY",
    "api_key_header": "x-api-key",
    "credit_tiers": [ {"tier_name": "default", "credits": 100000, "input_limit": 0, "output_limit": 0, "reset_frequency": "monthly"} ]
  }'
```

3) Create the API with safe defaults
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "orders",
    "api_version": "v1",
    "api_description": "Orders gateway",
    "api_allowed_roles": ["admin"],
    "api_allowed_groups": ["admin"],
    "api_servers": ["http://orders-api.internal:8080"],
    "api_type": "REST",
    "api_allowed_retry_count": 1,
    "api_allowed_headers": ["content-type", "accept"],
    "api_credits_enabled": true,
    "api_credit_group": "orders-upstream"
  }'
```

4) Add endpoints (only what you intend to expose)
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "orders", "api_version": "v1",
    "endpoint_method": "GET", "endpoint_uri": "/health",
    "endpoint_description": "Health check"
  }'

curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint" -d '{
    "api_name": "orders", "api_version": "v1",
    "endpoint_method": "POST", "endpoint_uri": "/orders",
    "endpoint_description": "Create order"
  }'
```

5) Subscribe a user (or your service account) to the API
```
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/subscription/subscribe" -d '{
    "username": "admin",
    "api_name": "orders",
    "api_version": "v1"
  }'
```

6) Call the gateway (cookie-based session)
```
curl -s -b "$COOKIE" "$BASE/api/rest/orders/v1/health"
```

7) Add endpoint validation (example: require `customerId` on create)
```
# 7.1 Get the endpoint_id (via UI or GET endpoint listing)
# 7.2 Attach a validation schema
curl -s -b "$COOKIE" -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/endpoint/endpoint/validation" -d '{
    "endpoint_id": "<endpoint_id>",
    "validation_enabled": true,
    "validation_schema": {"validation_schema": {"customerId": {"required": true, "type": "string", "min": 3}}}
  }'
```

Requests that fail validation return HTTP 400 without hitting the upstream.

## Troubleshooting
- 401 on gateway calls: ensure you’re logged in and cookies are sent (`access_token_cookie`).
- 403 on platform operations: your user needs the right role (e.g., `manage_apis`) or group.
- 404/GTW001/GTW003: API or endpoint mapping is missing; verify name/version/URI.
- CORS errors: tighten `ALLOWED_ORIGINS` and set `CORS_STRICT=true`.
- Secure cookies not set: confirm `HTTPS_ONLY=true` or `HTTPS_ENABLED=true` and correct `COOKIE_DOMAIN`.
