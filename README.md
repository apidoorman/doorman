
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
# IMPORTANT: Use strong, unique credentials. Never commit real credentials to version control.
DOORMAN_ADMIN_EMAIL=<your-admin-email>
DOORMAN_ADMIN_PASSWORD=<strong-password-12+chars>

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
# Example produces files like backend-services/generated/memory_dump-YYYYMMDDTHHMMSSZ.bin
MEM_DUMP_PATH=backend-services/generated/memory_dump.bin

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
```

Web client (Next.js)

```bash
cd web-client
cp .env.local.example .env.local
npm ci
npm run dev OR npm run build
```

## License Information
The contents of this repository are property of Doorman Dev, LLC.

Review the Apache License 2.0 for valid authorization of use.

[View License - Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)


## Disclaimer
Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations found in the source code.

##

We welcome contributors and testers!
