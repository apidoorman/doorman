![Logo](https://i.ibb.co/VpDyBMnk/doorman-gateway-logo.png)

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Release](https://img.shields.io/badge/release-v1.0.0-brightgreen)
![Last Commit](https://img.shields.io/github/last-commit/apidoorman/doorman)
![GitHub issues](https://img.shields.io/github/issues/apidoorman/doorman)

# Doorman API Gateway

A lightweight, Python-based API gateway for managing REST, SOAP, GraphQL, gRPC, and AI APIs. No low-level language expertise required.

![Example](https://i.ibb.co/jkwPWdnm/Image-9-26-25-at-10-12-PM.png)

## Key Features

- **Multi-Protocol Support**: REST, SOAP, GraphQL, gRPC, and AI APIs
- **Security**: User management, authentication, authorization, roles & groups
- **Traffic Control**: Rate limiting, throttling, dynamic routing, credits
- **Caching & Storage**: Redis caching, MongoDB integration, or in memory
- **Validation**: Request payload validation and logging

## Quick Start

### Prerequisites
- Docker installed
- Environment file (`.env`) at repo root (start from `./.env.example`)

### Run with Docker Compose

```bash
# 1) Prepare env (first time)
cp .env.example .env
# Edit .env and set: DOORMAN_ADMIN_EMAIL, DOORMAN_ADMIN_PASSWORD, JWT_SECRET_KEY

# 2) Start (builds automatically)
docker compose up
```

When ready:
- Web UI: `http://localhost:3000`
- Gateway API: `http://localhost:3001`

### One‑Command Demo (in‑memory + auto‑seed)

Spin up a preconfigured demo (auto‑cleans on exit) without editing `.env`:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up
```

Defaults:
- Admin: `demo@doorman.dev` / `DemoPassword123!`
- Web UI: `http://localhost:3000`
- API: `http://localhost:3001`
- Mode: in‑memory (no Redis/Mongo), demo data auto‑seeded in‑process on start
- Isolation: uses separate image tag (`doorman-demo:latest`) and project name to avoid overwriting any existing `doorman`
- Cleanup: containers, volumes, and networks are removed automatically when you stop (Ctrl+C)

## Frontend Gateway Configuration

The web client needs to know the backend gateway URL. Set `NEXT_PUBLIC_GATEWAY_URL` in the root `.env` file:

```bash
# For Docker Compose (default - both services in same container)
NEXT_PUBLIC_GATEWAY_URL=http://localhost:3001

# For production reverse proxy (frontend and API on same domain)
# Leave unset - frontend will use same origin
```

**Behavior:**
- If `NEXT_PUBLIC_GATEWAY_URL` is set → uses that URL for API calls
- If not set → uses same origin (for reverse proxy deployments where frontend and API share the same domain)

### Run in Background

```bash
# Start detached
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

## Configuration

### Required Environment Variables
- `DOORMAN_ADMIN_EMAIL` — initial admin user email
- `DOORMAN_ADMIN_PASSWORD` — initial admin password (12+ characters required)
- `JWT_SECRET_KEY` — secret key for JWT tokens (32+ chars)

Optional (recommended in some setups):
- `NEXT_PUBLIC_GATEWAY_URL` — frontend → gateway base URL (see “Frontend Gateway Configuration”)

### High Availability Setup

For production/HA with Redis and MongoDB via Docker Compose:

```bash
# In .env (compose service names inside the network)
MEM_OR_EXTERNAL=REDIS
MONGO_DB_HOSTS=mongo:27017
MONGO_DB_USER=doorman_admin
MONGO_DB_PASSWORD=changeme   # set a stronger password in real deployments
REDIS_HOST=redis

# Start with production profile (brings up Redis + MongoDB)
docker compose --profile production up -d
```

Notes:
- Ensure `MONGO_DB_USER`/`MONGO_DB_PASSWORD` match the values in `docker-compose.yml` (defaults are provided for convenience; change in production).
- When running under Compose, use `mongo` and `redis` service names (not `localhost`).

### Alternative: Manual Docker Commands

If you prefer not to use Docker Compose:

```bash
# Build the image
docker build -t doorman:latest .

# Run the container
docker run --rm --name doorman \
  -p 3001:3001 -p 3000:3000 \
  --env-file .env \
  doorman:latest
```

## Documentation

- User docs live in `user-docs/` with:
  - `01-getting-started.md` for setup and first API
  - `02-configuration.md` for environment variables
  - `03-security.md` for hardening
  - `04-api-workflows.md` for end-to-end examples
  - `05-operations.md` for production ops and runbooks
  - `06-tools.md` for diagnostics and the CORS checker


## Repository Structure

```
doorman/
├── backend-services/    # Python gateway core, routes, services, tests
├── web-client/         # Next.js frontend
├── docker/             # Container entrypoint and scripts
├── user-docs/          # Documentation and guides
├── scripts/            # Helper scripts (preflight, coverage, maintenance)
└── generated/          # Local development artifacts
```

## Security Notes

- Frontend only exposes `NEXT_PUBLIC_*` variables to the browser
- Never pass secrets to frontend build args
- Backend loads environment at runtime from `--env-file` or `/env/*.env`
- Platform/injected env variables take precedence over repo files

## License

Copyright Doorman Dev, LLC

Licensed under the Apache License 2.0 - see [LICENSE](https://www.apache.org/licenses/LICENSE-2.0)

## Disclaimer

Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations in the source code.

---

**We welcome contributors and testers!**
