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
- Environment file (`.env`) at repo root (use `./.env.example` as template)

### Run with Docker Compose (Recommended)

```bash
# Prepare env (first time)
cp .env.example .env
# Edit .env and set at least: DOORMAN_ADMIN_EMAIL, DOORMAN_ADMIN_PASSWORD, JWT_SECRET_KEY

# Start services (builds automatically)
docker compose up
```

**Access Points:**
- Backend API: `http://localhost:3001` (or your configured `PORT`)
- Web Client: `http://localhost:3000` (or your configured `WEB_PORT`)

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
- `DOORMAN_ADMIN_EMAIL`: Admin user email
- `DOORMAN_ADMIN_PASSWORD`: Admin password
- `JWT_SECRET_KEY`: Secret key for JWT tokens (32+ chars)

### High Availability Setup

For production/HA environments with Redis and MongoDB:

```bash
# Set in .env:
MEM_OR_EXTERNAL=REDIS

# Start with production profile (includes Redis + MongoDB)
docker compose --profile production up -d
```

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

## Testing

### Testing Against Docker

When testing from your host machine against Doorman running in Docker:

```bash
# Verbose output
make live-docker

# Quiet output
make liveq-docker

# Manual environment variable
DOORMAN_IN_DOCKER=1 make live
```

This configures test servers to use `host.docker.internal` (Mac/Windows) or `172.17.0.1` (Linux).

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
