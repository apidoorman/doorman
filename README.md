
![Logo](https://i.ibb.co/Y5T8g9y/pygate-logo-white.png)

##

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Pre-release](https://img.shields.io/badge/release-pre--release-yellow)
![Last Commit](https://img.shields.io/github/last-commit/pypeople-dev/pygate)
![GitHub issues](https://img.shields.io/github/issues/pypeople-dev/pygate)

One Platform for AI, REST, SOAP, GraphQL, gRPC and Websocket APIs. Fully managed with its own set of RESTful APIs. This is your APIs gateway to the world!


🔗 [pygate.org](https://pygate.org)


No specialized low-level language expertise required. Just a simple, cost-effective API Gateway built in Python. Keep it simple, scalable, and efficient while giving developers everything they need to manage APIs with ease. 🐍


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

## Releases
- v1.0.0 - REST Support (Latest - 16 April 2025)
- v1.1.0 - AI Support (To Be Announced)
- v1.1.0 - SOAP Support (To Be Announced)
- v1.3.0 - GraphQL Support (To Be Announced)
- v1.4.0 - gRPC Support (To Be Announced)
- v1.5.0 - Websocket Support (To Be Announced)


## Installation
Ensure you have a MongoDB server and redis running.

Install requirements

```bash
  pip install -r requirements.txt
```

Set environment variables
```bash
MONGO_DB_URI=mongodb://localhost:27017/pygate

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

JWT_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

ALLOWED_ORIGINS=http://localhost:5001
ALLOW_CREDENTIALS=true
ALLOW_METHODS=GET,POST,PUT,DELETE
ALLOW_HEADERS=*

PORT=5001
HTTPS_ONLY=False
COOKIE_DOMAIN=localhost
THREADS=1

PID_FILE=pygate.pid
```

Start pygate
    
```bash
  python pygate.py start
```

Stop pygate
    
```bash
  python pygate.py stop
```

Run pygate in console
    
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
