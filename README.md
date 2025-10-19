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
- **Traffic Control**: Rate limiting, throttling, dynamic routing
- **Caching & Storage**: Redis caching, MongoDB integration, or all in memory
- **Validation**: Request payload validation and logging

## Quick Start

### Prerequisites
- Docker installed
- Environment file (`.env`) at repo root (use `./backend-services/.env.example` as template)

### Run with Docker

```bash
# Build the image
docker build -t doorman:latest .

# Run the container
docker run --rm --name doorman \
  -p 3001:3001 -p 3000:3000 \
  --env-file .env \
  doorman:latest
```

**Access Points:**
- Backend API: http://localhost:3001
- Web Client: http://localhost:3000

### Run in Background

```bash
# Start detached
docker run -d --name doorman \
  -p 3001:3001 -p 3000:3000 \
  --env-file .env \
  doorman:latest

# View logs
docker logs -f doorman

# Stop container
docker stop doorman
```

## Configuration

### Required Environment Variables
- `DOORMAN_ADMIN_EMAIL`: Admin user email
- `DOORMAN_ADMIN_PASSWORD`: Admin password
- `JWT_SECRET_KEY`: Secret key for JWT tokens

### High Availability Setup
For production/HA environments:
- Set `MEM_OR_EXTERNAL=REDIS`
- Configure Redis connection details in `.env`

### Custom Ports

```bash
# Change web client port
docker run --rm --name doorman \
  -p 3001:3001 -p 3002:3002 \
  -e WEB_PORT=3002 \
  --env-file .env \
  doorman:latest
```

### Alternative: Mount Environment Folder

```bash
# Create env folder with config files
mkdir -p env

# Run with mounted env folder
docker run --rm --name doorman \
  -p 3001:3001 -p 3000:3000 \
  -v "$(pwd)/env:/env:ro" \
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
