# Doorman Gateway Engine

The core high-performance gateway engine for Doorman. Handles protocol translation, security enforcement, rate limiting, and observability for REST, GraphQL, gRPC, and SOAP APIs.

## 🚀 Key Features

- **Multi-Protocol Gateway**: First-class support for REST, SOAP 1.1/1.2, GraphQL, and gRPC (with auto-generation).
- **Security & RBAC**: Integrated JWT management, Role-Based Access Control, and User/Group isolation.
- **Traffic Control**: Granular rate limiting (fixed window), throttling, and credit-based quotas.
- **Storage Flexibility**: 
  - **Memory Mode**: Zero-dependency mode for local development and CI/CD.
  - **Production Mode**: Scalable architecture using Redis (caching/rate-limits) and MongoDB (persistence).
- **Robustness**: Built-in XXE protection, path traversal guards, and secure gRPC compilation.
- **Observability**: Structured logging, request tracing, and aggregated metrics.

---

## 🛠 Setup & Development

### 1. Instant Memory Mode (No Database)
Perfect for testing or local development.
```bash
# Set up environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run instantly (uses in-memory storage)
export DOORMAN_MEMORY_MODE=true
python doorman.py
```

### 2. Production/HA Mode
Requires Redis and MongoDB.
```bash
# Configure persistence
export MEM_OR_EXTERNAL=REDIS
export REDIS_HOST=localhost
export MONGO_DB_HOSTS=localhost:27017

# Run server
python doorman.py
```

### 3. One-Command Docker Demo
Run the full gateway + dashboard stack:
```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

---

## ⚙️ Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MEM_OR_EXTERNAL` | `REDIS` | Shared Redis cache plus MongoDB persistence; required by the Rust gateway. |
| `REDIS_HOST` | `localhost` | Redis server hostname. |
| `MONGO_DB_HOSTS` | `localhost:27017` | MongoDB connection string. |
| `JWT_SECRET_KEY` | - | **Required**. Secret for signing tokens. |
| `DOORMAN_ADMIN_PASSWORD` | - | **Required**. Admin password (min 12 chars). |
| `LOGS_DIR` | `./logs` | Directory for structured logs. |

---

## 🧪 Testing

We maintain high stability with over 480 integration tests.
```bash
# Run all tests
./venv/bin/pytest -q tests/

# Run specific suite
./venv/bin/pytest tests/test_gateway_soap.py
```

---

## 📂 Repository Structure

- `routes/`: API endpoint definitions (RESTful).
- `services/`: Core logic for protocol handling (REST, SOAP, GraphQL, gRPC).
- `middleware/`: Security, analytics, and body size limiters.
- `models/`: Pydantic models for request/response validation.
- `utils/`: shared utilities (auth, database, metrics, encryption).

---

Built by **Doorman Dev, LLC**. Licensed under **Apache License 2.0**.

## Rust Gateway Migration

Rust owns all public gateway traffic (`/api/*`, `/grpc-web/*`, and `/metrics`)
for REST, SOAP, GraphQL, native gRPC, and gRPC-Web. Python owns only
`/platform/*`; in the combined container it mounts only those routes and listens
on `127.0.0.1:${PYTHON_INTERNAL_PORT:-3002}`. There is no Python gateway fallback.

MongoDB and Redis are required shared dependencies for the deployed data plane.
Proto upload/update compiles a language-neutral descriptor set into the API
document. Startup backfills descriptors for existing active gRPC APIs; operators
can rerun this with `POST /platform/proto/descriptors/backfill`, and readiness
reports any APIs still missing descriptors. Rust writes redacted structured
activity records into the shared log directory so existing platform log queries
continue to include gateway traffic.
