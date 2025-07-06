
![Logo](https://i.ibb.co/mMcR63Q/doorman-logo-grn.png)

##

![api-gateway](https://img.shields.io/badge/API-Gateway-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Release](https://img.shields.io/badge/release-pre--release-orange)
![Last Commit](https://img.shields.io/github/last-commit/apidoorman/doorman)
![GitHub issues](https://img.shields.io/github/issues/apidoorman/doorman)

##

# Doorman API Gateway
A lightweight API gateway built for AI, REST, SOAP, GraphQL, and gRPC APIs. No specialized low-level language expertise required. Just a simple, cost-effective API Gateway built in Python. This is your application’s gateway to the world. 🐍

![Example](https://i.ibb.co/nZK8Pd9/example-dashboard-light.png)

## Features
Doorman supports user management, authentication, authorizaiton, dynamic routing, roles, groups, rate limiting, throttling, logging, redis caching, and mongodb. It allows you to manage REST, AI, SOAP, GraphQL, and gRPC APIs.


## Coming Enhancements
Doorman will soon support transformation, field encryption, and orchestration. More features to be announced.


## Documentation
[API Documentation](https://doorman.so/docs)
| [Postman collection](https://doorman.so/doorman-postman-collection.json)
| [OpenAPI swagger](https://doorman.so/openapi.json)


## Get Started
Doorman is simple to setup. Just have redis and mongo db running. Then follow the few steps below.

Clone Doorman repository

```bash
  git clone https://github.com/apidoorman/doorman.git
```

Install requirements

```bash
  pip install -r requirements.txt
```

Set environment variables in a .env file
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
PID_FILE=Doorman.pid
```

Create and give permissions to folders

```
mkdir -p proto generated && chmod 755 proto generated
```

Start Doorman background process
    
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


## License Information
The contents of this repository are property of doorman.so.

Review the Apache License 2.0 for valid authorization of use.

[View License - Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)


## Disclaimer
This project is under active development and is not yet ready for production environments.

Use at your own risk. By using this software, you agree to the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0) and any annotations found in the source code.

##

We welcome contributors and testers!