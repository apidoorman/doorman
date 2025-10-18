
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

![Example](https://i.ibb.co/jkwPWdnm/Image-9-26-25-at-10-12-PM.png)

## Features
Doorman supports user management, authentication, authorizaiton, dynamic routing, roles, groups, rate limiting, throttling, logging, redis caching, mongodb, and endpoint request payload validation. It allows you to manage REST, AI, SOAP, GraphQL, and gRPC APIs.

## Repository Structure
- `backend-services/`: Python gateway core, routes, services, tests, and runtime assets.
- `web-client/`: Next.js frontend (uses `next.config.mjs`).
- `docker/`: Entrypoint and container scripts.
- `user-docs/`: End-user documentation and guides.
- `scripts/`: Helper scripts (preflight, coverage, maintenance).
- `user-docs/examples/tests/`: Example tests previously at the repo root.
- `generated/`: Local dev artifacts (migrated into `backend-services/generated` at runtime).
- Dev shims moved to `scripts/test-shims/`: helper wrappers to run specific backend tests directly if desired.

## Launch With Docker
Ensure an env file exists at the repo root: `./.env` (use `./backend-services/.env.example` as a reference). Keep this file outside the image and pass it at runtime. Note - this is set for development, update variables and hosts to reflect a production environment.

### Testing Against Docker
When running tests from your **host machine** against Doorman running **inside Docker**, use the Docker-specific make targets:

```bash
# Run live tests against Doorman in Docker (verbose)
make live-docker

# Run live tests against Doorman in Docker (quiet)
make liveq-docker

# Or set the environment variable manually
DOORMAN_IN_DOCKER=1 make live
```

This ensures test servers use `host.docker.internal` (Mac/Win) or `172.17.0.1` (Linux) so Doorman can reach them from inside the container.

### Quickstart
See commands below.

```bash
# 1) Build the image
docker build -t doorman:latest .

# 2) Run the container (publishes backend 3001 and web 3000)
docker run --rm \
  --name doorman \
  -p 3001:3001 -p 3000:3000 \
  --env-file "$(pwd)/.env" \
  doorman:latest
```

- Backend: http://localhost:3001
- Web client: http://localhost:3000 (set `WEB_PORT` to change)

Detach and follow logs:

```bash
docker run -d --name doorman -p 3001:3001 -p 3000:3000 --env-file "$(pwd)/.env" doorman:latest
docker logs -f doorman
docker stop doorman
```

Override only the web port (optional):

```bash
docker run --rm --name doorman -p 3001:3001 -p 3002:3002 \
  -e WEB_PORT=3002 \
  --env-file "$(pwd)/.env" \
  doorman:latest
```

### Alternative: mount an /env folder

```bash
# Prepare your env folder (example: ./env/production.env)
docker build -t doorman:latest .
docker run --rm --name doorman -p 3001:3001 -p 3000:3000 -v "$(pwd)/env:/env:ro" doorman:latest
```

Notes
- The container loads env without overriding already-set variables. Platform/injected env and `/env/*.env` take precedence over repo files.
- Required secrets: `DOORMAN_ADMIN_EMAIL`, `DOORMAN_ADMIN_PASSWORD`, `JWT_SECRET_KEY`. For HA, set `MEM_OR_EXTERNAL=REDIS` and configure Redis.
 - The web client now uses `next.config.mjs`, so TypeScript is not required at runtime inside the container.

Frontend details
- Only NEXT_PUBLIC_* variables are exposed to the browser. Do not pass secrets.
- Build-args affect the frontend build output. Changing them requires a rebuild.
- The backend still reads its env at runtime from `--env-file` (or `/env/*.env`).

## License Information
The contents of this repository are property of Doorman Dev, LLC.

Review the Apache License 2.0 for valid authorization of use.

[View License - Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)


## Disclaimer
Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations found in the source code.

##

We welcome contributors and testers!
