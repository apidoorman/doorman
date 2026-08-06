![Logo](https://i.ibb.co/VpDyBMnk/doorman-gateway-logo.png)

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Release](https://img.shields.io/badge/release-v1.0.0-brightgreen)
![Last Commit](https://img.shields.io/github/last-commit/apidoorman/doorman)
![GitHub issues](https://img.shields.io/github/issues/apidoorman/doorman)

# Doorman API Gateway

Lightweight Python API gateway for REST, SOAP, GraphQL, gRPC, and AI APIs.

![Example](https://i.ibb.co/jkwPWdnm/Image-9-26-25-at-10-12-PM.png)

## Key Features

- **Multi-Protocol Support**: REST, SOAP, GraphQL, gRPC, and AI APIs
- **Security**: User management, authentication, authorization, roles & groups
- **Traffic Control**: Rate limiting, throttling, dynamic routing, credits
- **Caching & Storage**: Redis caching, MongoDB integration, or in memory
- **Validation**: Request payload validation and logging

## Quick Demo

Run a local demo instance in seconds.

```bash
# Clone and launch instantly
cp .env.demo .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

- **Web UI**: [http://localhost:3000](http://localhost:3000)
- **API**: [http://localhost:3001](http://localhost:3001)
- **Admin**: `demo@doorman.dev` / `DemoPassword123!`
- **Mode**: Memory mode (no external DB)

### Running Live Tests

With the demo running, run the full live test suite:

```bash
cd backend-services/live-tests && pytest
```

The tests auto-detect the backend port and credentials from `.env` — no extra env vars needed.

---

## Self-Hosting

Deploy with Docker. Production mode requires Redis and MongoDB.

### 1. Environment Configuration
Copy the template and set your secrets.
```bash
cp .env.example .env
# Set: DOORMAN_ADMIN_EMAIL, DOORMAN_ADMIN_PASSWORD, JWT_SECRET_KEY
```

### 2. Storage
MongoDB and Redis are required by the deployed gateway and start with Compose.

### 3. Launch
```bash
# Rust gateway + Python platform + Redis + MongoDB
docker compose up -d
```

---

## Configuration

### Core Environment Variables
| Variable | Required | Description |
| :--- | :--- | :--- |
| `DOORMAN_ADMIN_EMAIL` | Yes | Initial administrator email |
| `DOORMAN_ADMIN_PASSWORD` | Yes | Admin password (min 12 chars) |
| `JWT_SECRET_KEY` | Yes | Secret for signing access tokens |
| `NEXT_PUBLIC_GATEWAY_URL` | No | Frontend API target (Defaults to same origin) |
| `PYTHON_INTERNAL_PORT` | No | Internal Python `/platform/*` listener; defaults to `3002` |

### Persistence & Performance
- Redis stores shared policy counters, caches, tier rate limits, and gateway analytics.
- MongoDB stores gateway configuration, users, CRUD data, and compiled gRPC descriptors.
- Public REST, SOAP, GraphQL, native gRPC, and gRPC-Web requests run entirely in Rust; clients do not need an API contract change.
- Python is the internal `/platform/*` control plane only. There is no Python gateway fallback, shadow mode, or in-memory data-plane mode.
- Successful mutating platform calls publish a Redis policy revision so Rust workers refresh without waiting for the cache TTL.
- Volumes: Docker-managed volumes (`doorman-generated`, `doorman-logs`). Use `docker compose down -v` to reset.

---

## Repository Structure

```text
doorman/
├── gateway-rs/          # Rust public gateway and Python platform proxy
├── backend-services/    # Python platform APIs and gateway parity reference
├── web-client/         # Next.js Dashboard
├── user-docs/          # Technical Guides & Runbooks
├── scripts/            # Build & Maintenance tools
└── ops/                # Infrastructure & Docker config
```

## Documentation

Deep-dive into our guides for advanced setups:
- [Getting Started Guide](user-docs/01-getting-started.md)
- [Security & Hardening](user-docs/03-security.md)
- [API Workflows (gRPC/SOAP)](user-docs/04-api-workflows.md)
- [Production Operations](user-docs/05-operations.md)

---

## License

**Copyright © Doorman Dev, LLC**
Licensed under the **Apache License 2.0**.

Review the [Security Hardening Guide](user-docs/03-security.md) before production deployment.
