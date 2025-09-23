
![Logo](https://i.ibb.co/VpDyBMnk/doorman-gateway-logo.png)

##

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Release](https://img.shields.io/badge/release-v1.0.0-brightgreen)
![Last Commit](https://img.shields.io/github/last-commit/apidoorman/doorman)
![GitHub issues](https://img.shields.io/github/issues/apidoorman/doorman)

##

# Doorman API Gateway
A lightweight API gateway built for AI, REST, SOAP, GraphQL, and gRPC APIs. No specialized low-level language expertise required. Just a simple, cost-effective API Gateway built in Python. This is your application’s gateway to the world. 🐍

![Example](https://i.ibb.co/9dkgPLP/dashboardpage.png)

## Features
Doorman supports user management, authentication, authorizaiton, dynamic routing, roles, groups, rate limiting, throttling, logging, redis caching, mongodb, and endpoint request payload validation. It allows you to manage REST, AI, SOAP, GraphQL, and gRPC APIs.

## Coming Enhancements
Doorman will soon support transformation, field encryption, and orchestration. More features to be announced.

## Request Validation
Doorman can validate request payloads at the endpoint level before proxying to your upstream service.

- Scope: REST (JSON/XML), SOAP, GraphQL, and gRPC (JSON payload for gateway).
- Configure: Use the platform API to attach a validation schema to an endpoint.
- Behavior: If validation fails, the gateway responds with 400 and does not call the upstream.

Create a validation schema

```bash
curl -X POST -b /tmp/doorman_cookies.txt \
  -H 'Content-Type: application/json' \
  http://localhost:5001/platform/endpoint/endpoint/validation \
  -d '{
        "endpoint_id": "<endpoint_id>",
        "validation_enabled": true,
        "validation_schema": {
          "validation_schema": {
            "user.name": {"required": true, "type": "string", "min": 2}
          }
        }
      }'
```

Schema path examples
- REST (JSON): `user.name`, `items[0].price`
- SOAP: refer to elements within the SOAP Body operation element (namespaces are stripped). Example: `name` for `<Operation><name>...</name></Operation>`
- GraphQL: prefix with operation name. Example: `CreateUser.input.name` for `mutation CreateUser($input: UserInput!) { ... }`
- gRPC (gateway JSON): for `{ "message": { "user": { "name": "..." } } }` use `user.name`

Notes
- Enable/disable per-endpoint with `validation_enabled`.
- Schemas are cached and enforced in the gateway path before proxying.
- On failure, response code is 400 with a concise validation message.

## Get Started
Doorman is simple to setup. In production you should run Redis and (optionally) MongoDB. In memory-only mode, Doorman persists encrypted dumps to disk for quick restarts.

Clone Doorman repository

```bash
  git clone https://github.com/apidoorman/doorman.git
```

Install requirements (backend)

```bash
  cd backend-services
  pip install -r requirements.txt
```

Set environment variables in a .env file (see backend-services/.env.example)
```bash
# Startup admin should be used for setup only
STARTUP_ADMIN_EMAIL=admin@localhost.com
STARTUP_ADMIN_PASSWORD=SecPassword!12345

# Cache/database mode (unified flag)
# MEM for in-memory cache + in-memory DB; REDIS to use Redis-backed cache (DB can still be memory-only)
MEM_OR_EXTERNAL=MEM
MEM_ENCRYPTION_KEY=32+char-secret-used-to-encrypt-dumps

# Mongo DB Config
MONGO_DB_HOSTS=localhost:27017 # Comma separated
MONGO_REPLICA_SET_NAME=rs0

# Redis Config
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Memory Dump Config (memory-only mode)
# Base path/stem for encrypted in-memory database dumps (.bin). Timestamp is appended.
# Example produces files like generated/memory_dump-YYYYMMDDTHHMMSSZ.bin
MEM_DUMP_PATH=generated/memory_dump.bin

# Authorization Config
JWT_SECRET_KEY=please-change-me # REQUIRED: app will fail to start without this
TOKEN_ENCRYPTION_KEY=optional-secret-for-api-key-encryption

# HTTP Config
ALLOWED_ORIGINS=https://localhost:8443  # Comma separated
ALLOW_CREDENTIALS=True
ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD  # Comma separated
ALLOW_HEADERS=*  # Comma separated, allow all for now. Will set this per API
HTTPS_ONLY=True
COOKIE_DOMAIN=localhost # should match your origin host name

# Application Config
PORT=5001
THREADS=4
DEV_RELOAD=False # Helpful when running in console for debug
SSL_CERTFILE=./certs/localhost.crt # Update to your cert path if using HTTPS_ONLY
SSL_KEYFILE=./certs/localhost.key # Update to your key path if using HTTPS_ONLY
PID_FILE=doorman.pid
```

Create and give permissions to folders (inside backend-services)

```
cd backend-services && mkdir -p proto generated && chmod 755 proto generated
```

Start Doorman background process (from backend-services)
    
```bash
  python doorman.py start
```

Stop Doorman background process
    
```bash
  python doorman.py stop
```

Run Doorman console instance for debugging
    
```bash
  python doorman.py run

Web client (Next.js)

```bash
cd web-client
cp .env.local.example .env.local
npm ci
npm run dev
```

Defaults
- Backend: http://localhost:5001 (or set PORT in backend .env)
- Web: http://localhost:3000
- Frontend config: set `web-client/.env.local` → `NEXT_PUBLIC_SERVER_URL=http://localhost:3002` if your backend runs on 3002

## Docker
- Compose up: `docker compose up --build`
- Services: backend (`:5001`), web (`:3000`)
- Secrets: set `JWT_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `MEM_ENCRYPTION_KEY` via env/secret manager (avoid checking into git)
- Override backend envs: `docker compose run -e KEY=value backend ...`
- Reset volumes/logs: `docker compose down -v`

Smoke checks
- Liveness: `curl -s http://localhost:5001/platform/monitor/liveness` → `{ "status": "alive" }`
- Readiness: `curl -s http://localhost:5001/platform/monitor/readiness` → `{ status: "ready", ... }`
- Auth login: `curl -s -c /tmp/doorman_cookies.txt -H 'Content-Type: application/json' -d '{\"email\":\"admin@localhost\",\"password\":\"password1\"}' http://localhost:5001/platform/authorization`
- Auth status: `curl -s -b /tmp/doorman_cookies.txt http://localhost:5001/platform/authorization/status`
- One-liner: `BASE_URL=http://localhost:5001 STARTUP_ADMIN_EMAIL=admin@localhost STARTUP_ADMIN_PASSWORD=password1 bash scripts/smoke.sh`

Production notes
- Use Redis in production (`MEM_OR_EXTERNAL=REDIS`) for distributed rate limiting.
- In memory-only mode, run a single worker: `THREADS=1`.
- Prefer `LOG_FORMAT=json` for structured logs.

Production security defaults
- Set `CORS_STRICT=true` and explicitly whitelist your origins via `ALLOWED_ORIGINS`.
- Enable `HTTPS_ONLY=true` and `HTTPS_ENABLED=true` so cookies are Secure and CSRF validation is enforced.

Quick go-live checklist
- Start stack: `docker compose up --build`
- Verify health:
  - `curl -s http://localhost:5001/platform/monitor/liveness` → `{ "status": "alive" }`
  - `curl -s http://localhost:5001/platform/monitor/readiness` → `{ status: "ready", ... }`
- Smoke auth:
  - `curl -s -c /tmp/doorman_cookies.txt -H 'Content-Type: application/json' -d '{\"email\":\"admin@localhost\",\"password\":\"password1\"}' http://localhost:5001/platform/authorization`
  - `curl -s -b /tmp/doorman_cookies.txt http://localhost:5001/platform/authorization/status`
- Web: Ensure `web-client/.env.local` has `NEXT_PUBLIC_SERVER_URL=http://localhost:5001`, then `npm run build && npm start` (or use compose service `web`).

Optional: run `bash scripts/smoke.sh` (uses `BASE_URL`, `STARTUP_ADMIN_EMAIL`, `STARTUP_ADMIN_PASSWORD`).

## Demo Data Seeder
- Populate the platform with realistic random data (users, APIs, endpoints, roles, groups, tokens, subscriptions, logs, protos) for UI exploration.

Run from repo root:

```
python backend-services/scripts/seed_demo_data.py --users 40 --apis 15 --endpoints 6 --protos 6 --logs 1500
```

Flags:
- `--users` count (default 30)
- `--apis` count (default 12)
- `--endpoints` per-API (default 5)
- `--groups` extra groups (default 6)
- `--protos` proto files (default 5)
- `--logs` log lines to append (default 1000)
- `--seed` RNG seed for reproducibility

Notes:
- Works with memory-only or MongoDB modes. Metrics (for the dashboard) are in-memory and will reset on server restart; re-run the seeder to repopulate.
- Admin user is preserved; additional roles/groups are added if missing.
- Proto files are written under `backend-services/proto/` (no external tooling required to view in UI).


## License Information
The contents of this repository are property of doorman.so.

Review the Apache License 2.0 for valid authorization of use.

[View License - Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)


## Disclaimer
Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations found in the source code.

##

We welcome contributors and testers!
