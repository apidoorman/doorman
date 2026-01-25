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
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

- **Web UI**: [http://localhost:3000](http://localhost:3000)
- **Admin**: `demo@doorman.dev` / `DemoPassword123!`
- **Mode**: Memory mode (no external DB)

---

## Self-Hosting

Deploy with Docker. Production mode requires Redis and MongoDB.

### 1. Environment Configuration
Copy the template and set your secrets.
```bash
cp .env.example .env
# Set: DOORMAN_ADMIN_EMAIL, DOORMAN_ADMIN_PASSWORD, JWT_SECRET_KEY
```

### 2. Choose Storage
- Memory (default): development and tests.
- Redis + MongoDB: production.

### 3. Launch
```bash
# Standard launch
docker compose up -d

# Production launch (Redis + MongoDB)
docker compose --profile production up -d
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

### Persistence & Performance
- Redis: set `MEM_OR_EXTERNAL=REDIS` to enable caching/rate limiting.
- MongoDB: set `MONGO_DB_HOSTS=mongo:27017` (and credentials) to persist configurations and users.
- Volumes: Docker-managed volumes (`doorman-generated`, `doorman-logs`). Use `docker compose down -v` to reset.

---

## Repository Structure

```text
doorman/
├── backend-services/    # Python Gateway Engine (FastAPI)
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
