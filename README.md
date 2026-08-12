![Doorman logo](web-client/public/doorman-mark.svg)

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Rust](https://img.shields.io/badge/Rust-1.88-orange)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Last Commit](https://img.shields.io/github/last-commit/apidoorman/doorman)
![GitHub issues](https://img.shields.io/github/issues/apidoorman/doorman)

# Doorman API Gateway

A Rust API gateway and control plane for REST, SOAP, GraphQL, gRPC, gRPC-Web, and AI APIs.

## Key features

- Multi-protocol gateway: REST, SOAP, GraphQL, native gRPC, and gRPC-Web
- Native control plane: authentication, users, APIs, endpoints, roles, groups, routing, subscriptions, credits, tiers, quotas, security, discovery, and monitoring
- Traffic policy: rate limits, throttling, bandwidth limits, routing, retries, circuit breaking, credits, and schema validation
- Dual storage: a self-contained in-memory mode or shared MongoDB and Redis
- Encrypted in-memory snapshots compatible with the former DMP1 dump format
- Next.js management UI served alongside the Rust service

## Control plane

The built-in control plane keeps gateway configuration, request operations, and security controls in one self-hosted interface.

### API catalog

![Doorman API catalog](docs/images/doorman-apis.png)

Define and organize the APIs exposed through the gateway, including their versions, protocols, and endpoints.

### User management

Manage users, roles, groups, and access permissions from the control plane.

### Analytics

Monitor API usage, performance, errors, and traffic trends with built-in analytics.

## Get Started: Quick Demo

```bash
cp .env.demo .env
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

- Web UI: [http://localhost:3000](http://localhost:3000)
- Gateway and platform API: [http://localhost:3001](http://localhost:3001)
- Admin: `demo@doorman.dev` / `DemoPassword123!`
- Storage: in memory; MongoDB and Redis are not required

## Get Started: Self-Hosting

Copy the template, replace every development secret, and launch:

```bash
cp .env.example .env
docker compose up -d --build
```

The default is `MEM_OR_EXTERNAL=MEM`. For a shared, multi-instance deployment:

```bash
MEM_OR_EXTERNAL=REDIS docker compose --profile external up -d --build
```

Shared mode uses MongoDB for durable configuration and Redis for caches, counters, revocations, routing state, and analytics.

### Configuration

| Variable | Required | Description |
| :--- | :--- | :--- |
| `DOORMAN_ADMIN_EMAIL` | Yes | Initial administrator email |
| `DOORMAN_ADMIN_PASSWORD` | Yes | Initial administrator password |
| `JWT_SECRET_KEY` or `JWT_KEYS` | Yes | Access-token signing configuration |
| `MEM_OR_EXTERNAL` | No | `MEM` (default) or `REDIS` for MongoDB plus Redis |
| `MEM_ENCRYPTION_KEY` | In memory mode | Encrypts automatic and manual DMP1 snapshots |
| `MEM_DUMP_PATH` | No | Snapshot path hint; defaults to `data/memory_dump.bin` |
| `NEXT_PUBLIC_GATEWAY_URL` | No | Browser gateway target; same-origin by default |

Public protocol URLs and `/platform/*` API contracts remain unchanged. There is no legacy-process proxy or fallback in the runtime image.

## Repository structure

```text
doorman/
├── gateway-rs/             # Rust gateway and control plane
├── web-client/             # Next.js dashboard
├── parity/                 # Frozen pre-Rust public contract fixtures
├── user-docs/              # Guides and runbooks
├── scripts/                # Build and operational helpers
└── ops/                    # Infrastructure configuration
```

## Documentation

- [Getting Started](user-docs/01-getting-started.md)
- [Configuration](user-docs/02-configuration.md)
- [Security and Hardening](user-docs/03-security.md)
- [API Workflows](user-docs/04-api-workflows.md)
- [Production Operations](user-docs/05-operations.md)
- [Testing](user-docs/TESTS.md)

## License

Copyright © Doorman Dev, LLC. Licensed under the Apache License 2.0.
