
![Logo](https://i.ibb.co/Y5T8g9y/pygate-logo-white.png)

##

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Pre-release](https://img.shields.io/badge/release-pre--release-yellow)
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

🔗 [Postman collection](https://pygate.org/docs/pm/v1.0.0)

🔗 [OpenAPI swagger](https://pygate.org/docs/openapi/v1.0.0)


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
# Mongo DB Config
MONGO_DB_URI=mongodb://localhost:27017/pygate
`
# Redis Config
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Authorization Config
JWT_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# HTTP Config
ALLOWED_ORIGINS=https://localhost:8443,https://localhost:9000
ALLOW_CREDENTIALS=true
ALLOW_METHODS=GET,POST,PUT,DELETE
ALLOW_HEADERS=Authorization,Clieny-Key
HTTPS_ONLY=True
COOKIE_DOMAIN=localhost

# Application Config
PORT=8443
THREADS=4
SSL_CERTFILE=./certs/localhost.crt
SSL_KEYFILE=./certs/localhost.key
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
