# Security Guide

Comprehensive security features and best practices for Doorman API Gateway.

## Overview

Doorman implements defense-in-depth security with multiple layers:

- Transport Layer Security (HTTPS/TLS)
- Authentication and authorization (JWT, RBAC)
- CSRF protection
- CORS policies (platform and per-API)
- IP access control (global and per-API)
- Request validation and size limits
- Security headers
- Audit logging and request tracking
- Encryption at rest

---

## Transport Layer Security

### HTTPS Enforcement

**Production Guard**: When `ENV=production`, Doorman refuses to start unless HTTPS is configured.

```bash
# TLS terminated at reverse proxy (Nginx, Traefik, Caddy, ALB, etc.)
HTTPS_ONLY=true  # Enforces secure cookies and CSRF validation
```

**Security behaviors when HTTPS is enabled:**
- Cookies marked with `Secure` flag (sent only over HTTPS)
- CSRF validation enforced
- HSTS headers sent automatically
- CSP and security headers applied

### HTTP Strict Transport Security (HSTS)

**Auto-enabled** when `HTTPS_ONLY=true`:
```
Strict-Transport-Security: max-age=15552000; includeSubDomains; preload
```

---

## Authentication and Authorization

### JWT Cookie-Based Authentication

Doorman uses **HttpOnly cookies** to store JWT tokens, preventing XSS attacks:

- **Access token**: Short-lived (default 30 minutes)
- **Refresh token**: Longer-lived (default 7 days)
- Both stored in `HttpOnly` cookies (not accessible via JavaScript)

### Role-Based Access Control (RBAC)

Users are assigned roles that grant specific permissions: `manage_apis`, `manage_users`, `view_logs`, `manage_security`, etc.

---

## CSRF Protection

Double-submit cookie pattern, auto-enforced when `HTTPS_ONLY=true`.

1. Server sets `csrf_token` cookie on login (not HttpOnly)
2. Client sends the value in `X-CSRF-Token` header
3. Server validates equality

---

## CORS Security

Platform CORS controls `/platform/*` (admin/config APIs), and each gateway API can define its own CORS policy.

**Best practices:**
- Avoid wildcard `*` with credentials
- Use `CORS_STRICT=true` in production
- List explicit origins, headers, and methods

---

## IP Access Control

Global and per-API whitelists/blacklists, with trusted proxy support for XFF.

**Precedence:**
1. Blacklist first (deny if matched)
2. Whitelist (if configured, allow-only within whitelist)

---

## Security Headers

Doorman sends modern security headers (CSP, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) by default.

---

## Encryption and Secrets

- `TOKEN_ENCRYPTION_KEY` for API key encryption at rest
- `MEM_ENCRYPTION_KEY` for memory dump encryption
- Strong `JWT_SECRET_KEY` for signing tokens

---

## Production Checklist (abridged)

- `ENV=production`, `HTTPS_ONLY=true`
- Set strong secrets (`JWT_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `MEM_ENCRYPTION_KEY`)
- `CORS_STRICT=true` with explicit `ALLOWED_ORIGINS`
- Disable `LOCAL_HOST_IP_BYPASS`
- Use `LOG_FORMAT=json`
- Configure IP policies and body size limits
- Use Redis/Mongo in HA setups
