
![Logo](https://i.ibb.co/VpDyBMnk/doorman-gateway-logo.png)

##

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Release](https://img.shields.io/badge/release-pre--release-orange)
![Last Commit](https://img.shields.io/github/last-commit/apidoorman/doorman)
![GitHub issues](https://img.shields.io/github/issues/apidoorman/doorman)

##

# Doorman API Gateway
A lightweight API gateway built for AI, REST, SOAP, GraphQL, and gRPC APIs. No specialized low-level language expertise required. Just a simple, cost-effective API Gateway built in Python. This is your application’s gateway to the world. 🐍

![Example](https://i.ibb.co/9dkgPLP/dashboardpage.png)

## Features
Doorman supports user management, authentication, authorizaiton, dynamic routing, roles, groups, rate limiting, throttling, logging, redis caching, and mongodb. It allows you to manage REST, AI, SOAP, GraphQL, and gRPC APIs.

## Coming Enhancements
Doorman will soon support transformation, field encryption, and orchestration. More features to be announced.

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
- Services: backend (`:5001`), web (`:3000`), redis (`:6379`)
- Secrets: set `JWT_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `MEM_ENCRYPTION_KEY` via env/secret manager (avoid checking into git)
- Override backend envs: `docker compose run -e KEY=value backend ...`
- Reset volumes/logs: `docker compose down -v`

Smoke checks
- Liveness: `curl -s http://localhost:5001/platform/monitor/liveness` → `{ "status": "alive" }`
- Readiness: `curl -s http://localhost:5001/platform/monitor/readiness` → `{ status: "ready", ... }`
- Auth login: `curl -s -c cookies.txt -H 'Content-Type: application/json' -d '{"email":"admin@localhost","password":"password1"}' http://localhost:5001/platform/authorization`
- Auth status: `curl -s -b cookies.txt http://localhost:5001/platform/authorization/status`
- One-liner: `BASE_URL=http://localhost:5001 STARTUP_ADMIN_EMAIL=admin@localhost STARTUP_ADMIN_PASSWORD=password1 bash scripts/smoke.sh`

Production notes
- Use Redis in production (`MEM_OR_EXTERNAL=REDIS`) for distributed rate limiting.
- In memory-only mode, run a single worker: `THREADS=1`.
- Optional: set `LOG_FORMAT=json` for structured logs.

Production security defaults
- Set `CORS_STRICT=true` and explicitly whitelist your origins via `ALLOWED_ORIGINS`.
- Enable `HTTPS_ONLY=true` and `HTTPS_ENABLED=true` so cookies are Secure and CSRF validation is enforced.

Quick go-live checklist
- Start stack: `docker compose up --build`
- Verify health:
  - `curl -s http://localhost:5001/platform/monitor/liveness` → `{ "status": "alive" }`
  - `curl -s http://localhost:5001/platform/monitor/readiness` → `{ status: "ready", ... }`
- Smoke auth:
  - `curl -s -c cookies.txt -H 'Content-Type: application/json' -d '{"email":"admin@localhost","password":"password1"}' http://localhost:5001/platform/authorization`
  - `curl -s -b cookies.txt http://localhost:5001/platform/authorization/status`
- Web: Ensure `web-client/.env.local` has `NEXT_PUBLIC_SERVER_URL=http://localhost:5001`, then `npm run build && npm start` (or use compose service `web`).

Optional: run `bash scripts/smoke.sh` (uses `BASE_URL`, `STARTUP_ADMIN_EMAIL`, `STARTUP_ADMIN_PASSWORD`).
```

## Web UI
Utilize the built in web interface for ease of use!

![Create APIs](https://i.ibb.co/j9vQJGL0/apispage.png)

![Custom Routings](https://i.ibb.co/D0CCYGJ/routespage.png)

![Edit Roles](https://i.ibb.co/jk2F7vk8/rolespage.png)

![Add Groups](https://i.ibb.co/1G3jMPvG/groupspage.png)

![User Management](https://i.ibb.co/3y2xVTv5/userspage.png)

![Advanced Logs](https://i.ibb.co/BKvVhW4B/logspage.png)


## License Information
The contents of this repository are property of doorman.so.

Review the Apache License 2.0 for valid authorization of use.

[View License - Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)


## Disclaimer
This project is under active development and is not yet ready for production environments.

Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations found in the source code.

##

We welcome contributors and testers!
