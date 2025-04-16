
![Logo](https://i.ibb.co/Y5T8g9y/pygate-logo-white.png)

##

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Release](https://img.shields.io/badge/release-v1.0.0-green)
![Last Commit](https://img.shields.io/github/last-commit/pypeople-dev/pygate)
![GitHub issues](https://img.shields.io/github/issues/pypeople-dev/pygate)

A lightweight API gateway for AI, REST, SOAP, GraphQL, gRPC, and WebSocket APIs — fully managed with built-in RESTful APIs for configuration and control. This is your application’s gateway to the world.

🔗 [pygate.org](https://pygate.org)

No specialized low-level language expertise required. Just a simple, cost-effective API Gateway built in Python. 🐍


## Features
- ✅ Authentication & Authorization
- ✅ Dynamic Routing
- ✅ Role & Group Management
- ✅ Rate Limiting & Throttling
- ✅ Logging & Monitoring
- ✅ Caching with Redis
- ✅ MongoDB Integration
- ✅ REST Support
- 🔜 AI Support
- 🔜 SOAP Support
- 🔜 GraphQL Support
- 🔜 gRPC Support
- 🔜 WebSocket Support
- 🔜 Request Validation
- 🔜 Transformation
- 🔜 Field Encryption
- 🔜 Orchestration


## Releases
- [v1.0.0 - REST Support](https://github.com/pygate-dev/pygate/releases) (Latest - 16 April 2025)
- v1.1.0 - AI Support (To Be Announced)


## Documentation
🔗 [API documentation](https://pygate.org/docs)

🔗 [Postman collection](https://pygate.org/pygate-postman-collection.json)

🔗 [OpenAPI swagger](https://pygate.org/openapi.json)


## Installation
Ensure you have a MongoDB server and redis running.

Clone pygate repository

```bash
  git clone https://github.com/pygate-dev/pygate.git
```

Install requirements

```bash
  pip install -r requirements.txt
```

Set environment variables
```bash
# Startup admin should be used for setup only
STARTUP_ADMIN_EMAIL=admin@localhost.com
STARTUP_ADMIN_PASSWORD=SecPassword!12345

# Mongo DB Config
MONGO_DB_HOSTS=localhost:27017 # Comma separated
MONGO_REPLICA_SET_NAME=rs0

# Redis Config
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Authorization Config
JWT_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# HTTP Config
ALLOWED_ORIGINS=https://localhost:8443  # Comma separated
ALLOW_CREDENTIALS=True
ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD  # Comma separated
ALLOW_HEADERS=*  # Comma separated, allow all for now. Will set this per API
HTTPS_ONLY=True
COOKIE_DOMAIN=localhost # should match your origin host name

# Application Config
PORT=8443
THREADS=4
DEV_RELOAD=False # Helpful when running in console for debug
SSL_CERTFILE=./certs/localhost.crt # Update to your cert path if using HTTPS_ONlY
SSL_KEYFILE=./certs/localhost.key # Update to your key path if using HTTPS_ONlY
PID_FILE=pygate.pid
```

Start pygate background process
    
```bash
  python pygate.py start
```

Stop pygate background process
    
```bash
  python pygate.py stop
```

Run pygate console instance
    
```bash
  python pygate.py run
```


## License Information
The contents of this repository are property of pygate.org.

Review the Apache License 2.0 for valid authorization of use.

[View License - Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)


## Disclaimer
This project is under active development and is not yet ready for production environments.

Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations found in the source code.

We welcome contributors and testers!
