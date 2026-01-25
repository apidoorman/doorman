# Doorman Backend Services

The core gateway engine for Doorman. Handles protocol translation, authentication, rate limiting, and observability for REST, GraphQL, gRPC, and SOAP.

## Features
- **Multiprotocol**: First-class support for REST, GraphQL, gRPC, and SOAP.
- **Auth Engine**: Built-in JWT management, RBAC, and User/Group/Role isolation.
- **Zero-Dependency Mode**: Run entirely in-memory for local dev.
- **Production Mode**: Connect to Redis (caching) and MongoDB (persistence) for scale.
- **Security First**: Integrated XXE protection (defusedxml), path traversal guards, and secure gRPC generation.

## Quick Start (Instant Dev Mode)

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run with Memory Storage**
   ```bash
   # No Redis or MongoDB required
   export DOORMAN_MEMORY_MODE=true
   python doorman.py
   ```

3. **Check Health**
   ```bash
   curl http://localhost:8000/health
   ```

## Configuration
Configure via environment variables or a `config.yaml` file. Key variables:
- `DOORMAN_REDIS_URL`: Connection string for Redis (default: localhost:6379)
- `DOORMAN_MONGO_URL`: Connection string for MongoDB (default: localhost:27017)
- `JWT_SECRET`: Secret key for signing tokens.

## Testing
We use `pytest` for comprehensive integration and unit testing.
```bash
# Run all tests (requires venv)
./venv/bin/pytest -q
```

---
Built by Doorman Dev, LLC. Licensed under Apache 2.0.
