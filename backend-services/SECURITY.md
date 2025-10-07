# Security Features & Posture

This document outlines the security features implemented in Doorman API Gateway.

## 🔒 Transport Layer Security

### HTTPS Enforcement
- **Production Guard**: In production (`ENV=production`), the application enforces HTTPS configuration
- **Startup Validation**: Server refuses to start unless `HTTPS_ONLY` or `HTTPS_ENABLED` is set to `true`
- **Secure Cookies**: Cookies are marked as `Secure` when HTTPS is enabled
- **SSL/TLS Configuration**: Supports custom certificate paths via `SSL_CERTFILE` and `SSL_KEYFILE`

```bash
# Production configuration (required)
ENV=production
HTTPS_ONLY=true
SSL_CERTFILE=./certs/server.crt
SSL_KEYFILE=./certs/server.key
```

### HTTP Strict Transport Security (HSTS)
- **Auto-enabled**: When `HTTPS_ONLY=true`, HSTS headers are automatically added
- **Default Policy**: `max-age=15552000; includeSubDomains; preload` (6 months)
- **Browser Protection**: Prevents downgrade attacks and ensures HTTPS-only access

## 🛡️ Authentication & Authorization

### JWT Cookie-Based Authentication
- **HTTP-Only Cookies**: Tokens stored in `HttpOnly` cookies to prevent XSS
- **Configurable Expiry**:
  - Access tokens: Default 30 minutes (configurable via `AUTH_EXPIRE_TIME`)
  - Refresh tokens: Default 7 days (configurable via `AUTH_REFRESH_EXPIRE_TIME`)
- **Token Revocation**:
  - In-memory blacklist with optional Redis persistence
  - Database-backed revocation for memory-only mode
  - Per-user and per-JTI revocation support

### CSRF Protection (Double Submit Cookie Pattern)
- **HTTPS-Only**: CSRF validation automatically enabled when `HTTPS_ENABLED=true`
- **Validation Flow**:
  1. Server sets `csrf_token` cookie on login
  2. Client sends `X-CSRF-Token` header with requests
  3. Server validates header matches cookie value
- **401 Response**: Invalid or missing CSRF tokens are rejected
- **Test Coverage**: Full test suite in `tests/test_auth_csrf_https.py`

```python
# CSRF validation (automatic when HTTPS enabled)
https_enabled = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true'
if https_enabled:
    csrf_header = request.headers.get('X-CSRF-Token')
    csrf_cookie = request.cookies.get('csrf_token')
    if not await validate_csrf_double_submit(csrf_header, csrf_cookie):
        raise HTTPException(status_code=401, detail='Invalid CSRF token')
```

## 🌐 CORS & Cross-Origin Security

### Platform Routes CORS
- **Environment-Based**: Configured via `ALLOWED_ORIGINS`, `ALLOW_METHODS`, `ALLOW_HEADERS`
- **Credentials Support**: Configurable via `ALLOW_CREDENTIALS`
- **Wildcard Safety**: Automatic downgrade to `localhost` when credentials are enabled with `*` origin
- **OPTIONS Preflight**: Full preflight handling with proper headers

### Per-API CORS (Gateway Routes)
- **API-Level Control**: Each API can define its own CORS policy
- **Configuration Options**:
  - `api_cors_allow_origins`: List of allowed origins (default: `['*']`)
  - `api_cors_allow_methods`: Allowed HTTP methods
  - `api_cors_allow_headers`: Allowed request headers
  - `api_cors_allow_credentials`: Enable credentials (default: `false`)
  - `api_cors_expose_headers`: Headers exposed to client
- **Preflight Validation**: Origin, method, and header validation before allowing requests
- **Dynamic Headers**: CORS headers computed per request based on API config

```python
# Per-API CORS example
{
  "api_cors_allow_origins": ["https://app.example.com"],
  "api_cors_allow_methods": ["GET", "POST"],
  "api_cors_allow_credentials": true,
  "api_cors_expose_headers": ["X-Request-ID", "X-RateLimit-Remaining"]
}
```

## 🚧 IP Policy & Access Control

### Global IP Filtering
- **Whitelist Mode**: `ip_whitelist` - Only listed IPs/CIDRs allowed (blocks all others)
- **Blacklist Mode**: `ip_blacklist` - Listed IPs/CIDRs blocked (allows all others)
- **CIDR Support**: Full IPv4 and IPv6 CIDR notation support
- **X-Forwarded-For**: Configurable trust via `trust_x_forwarded_for` setting
- **Trusted Proxies**: Validate XFF headers against `xff_trusted_proxies` list
- **Localhost Bypass**: Optional bypass for localhost (`LOCAL_HOST_IP_BYPASS=true`)

### Per-API IP Policy
- **API-Level Override**: Each API can define additional IP restrictions
- **Deny/Allow Lists**: API-specific `api_ip_deny_list` and `api_ip_allow_list`
- **Granular Control**: Restrict access to specific APIs by client IP
- **Audit Trail**: All IP denials logged with details (reason, XFF header, source IP)

```python
# IP policy enforcement
if client_ip:
    if whitelist and not ip_in_list(client_ip, whitelist):
        audit(request, action='ip.global_deny', target=client_ip,
              status='blocked', details={'reason': 'not_in_whitelist'})
        return 403  # Forbidden
```

## 🔐 Security Headers

### Content Security Policy (CSP)
- **Safe Default**: Restrictive baseline policy prevents common attacks
- **Default Policy**:
  ```
  default-src 'none';
  frame-ancestors 'none';
  base-uri 'none';
  form-action 'self';
  img-src 'self' data:;
  connect-src 'self';
  ```
- **Customizable**: Override via `CONTENT_SECURITY_POLICY` environment variable
- **XSS Protection**: Prevents inline scripts and untrusted resource loading

### Additional Security Headers
All responses include:
- **X-Content-Type-Options**: `nosniff` - Prevents MIME sniffing
- **X-Frame-Options**: `DENY` - Prevents clickjacking
- **Referrer-Policy**: `no-referrer` - Prevents referrer leakage
- **Permissions-Policy**: Restricts geolocation, microphone, camera access

```python
# Automatic security headers middleware
response.headers.setdefault('X-Content-Type-Options', 'nosniff')
response.headers.setdefault('X-Frame-Options', 'DENY')
response.headers.setdefault('Referrer-Policy', 'no-referrer')
response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
```

## 📝 Audit Trail & Logging

### Request ID Propagation
- **Auto-Generation**: UUID generated for each request if not provided
- **Header Support**: Accepts `X-Request-ID`, `Request-ID`, or generates new
- **Response Headers**: ID included in both `X-Request-ID` and `request_id` headers
- **Log Correlation**: All logs tagged with request ID for tracing
- **Middleware**: Automatic injection via `request_id_middleware`

### Audit Trail Logging
- **Separate Log File**: `doorman-trail.log` for audit events
- **Structured Logging**: JSON or plain text format (configurable)
- **Event Tracking**:
  - User authentication (login, logout, token refresh)
  - Authorization changes (role/group modifications)
  - IP policy violations
  - Configuration changes
  - Security events
- **Context Capture**: Username, action, target, status, details

### Log Redaction
- **Sensitive Data Protection**: Automatic redaction of:
  - Authorization headers: `Authorization: Bearer [REDACTED]`
  - Access tokens: `access_token": "[REDACTED]"`
  - Refresh tokens: `refresh_token": "[REDACTED]"`
  - Passwords: `password": "[REDACTED]"`
  - Cookies: `Cookie: [REDACTED]`
  - CSRF tokens: `X-CSRF-Token: [REDACTED]`
- **Pattern-Based**: Regex patterns match various formats
- **Applied Universally**: File and console logs both protected

```python
# Redaction filter (automatic)
PATTERNS = [
    re.compile(r'(?i)(authorization\s*[:=]\s*)([^;\r\n]+)'),
    re.compile(r'(?i)(access[_-]?token\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)'),
    re.compile(r'(?i)(password\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)'),
    # ... additional patterns
]
```

## 📏 Request Validation & Limits

### Body Size Limits
- **Default Limit**: 1MB (`MAX_BODY_SIZE_BYTES=1048576`)
- **Universal Enforcement**: All request types protected (REST, SOAP, GraphQL, gRPC)
- **Content-Length Based**: Efficient pre-validation before reading body
- **Per-API Type Overrides**:
  - `MAX_BODY_SIZE_BYTES_REST` - REST API override
  - `MAX_BODY_SIZE_BYTES_SOAP` - SOAP/XML API override (e.g., 2MB for large SOAP envelopes)
  - `MAX_BODY_SIZE_BYTES_GRAPHQL` - GraphQL query override
  - `MAX_BODY_SIZE_BYTES_GRPC` - gRPC payload override
- **Protected Paths**:
  - `/platform/authorization` - Prevents auth route DoS
  - `/api/rest/*` - REST APIs with custom limit
  - `/api/soap/*` - SOAP/XML APIs with custom limit
  - `/api/graphql/*` - GraphQL queries with custom limit
  - `/api/grpc/*` - gRPC payloads with custom limit
  - `/platform/*` - All platform routes
- **Audit Logging**: Violations logged to audit trail with details
- **Error Response**: 413 Payload Too Large with error code `REQ001`

```bash
# Example: Larger limit for SOAP APIs with big XML envelopes
MAX_BODY_SIZE_BYTES=1048576           # Default: 1MB
MAX_BODY_SIZE_BYTES_SOAP=2097152      # SOAP: 2MB
MAX_BODY_SIZE_BYTES_GRAPHQL=524288    # GraphQL: 512KB (queries are smaller)
```

### Request Validation Flow
- **Content-Length Check**: Validates header before reading body
- **Early Rejection**: Prevents large payloads from consuming resources
- **Type-Aware**: Different limits for different API types
- **Security Audit**: All rejections logged with content type and path

```python
# Body size validation
MAX_BODY_SIZE = int(os.getenv('MAX_BODY_SIZE_BYTES', 1_048_576))
if content_length and int(content_length) > MAX_BODY_SIZE:
    return ResponseModel(
        status_code=413,
        error_code='REQ001',
        error_message='Request entity too large'
    )
```

## 🔑 Encryption & Secrets

### API Key Encryption
- **At-Rest Encryption**: Optional encryption via `TOKEN_ENCRYPTION_KEY`
- **Transparent**: Encrypt/decrypt on read/write operations
- **Key Storage**: API keys can be encrypted in database/memory

### Memory Dump Encryption
- **Required for Dumps**: `MEM_ENCRYPTION_KEY` must be set for memory dumps
- **AES Encryption**: Secure encryption of serialized state
- **Key Derivation**: Uses Fernet (symmetric encryption)
- **Startup Restore**: Automatic decryption on server restart

```bash
# Encryption configuration
TOKEN_ENCRYPTION_KEY=your-api-key-encryption-secret-32chars+
MEM_ENCRYPTION_KEY=your-memory-dump-encryption-secret-32chars+
```

## 🛠️ Security Best Practices

### Production Checklist
- [ ] `ENV=production` set
- [ ] `HTTPS_ONLY=true` or `HTTPS_ENABLED=true` configured
- [ ] Valid SSL certificates configured (`SSL_CERTFILE`, `SSL_KEYFILE`)
- [ ] `JWT_SECRET_KEY` set to strong random value (change default!)
- [ ] `MEM_ENCRYPTION_KEY` set to strong random value (32+ chars)
- [ ] `ALLOWED_ORIGINS` configured (no wildcard `*`)
- [ ] `CORS_STRICT=true` enforced
- [ ] IP whitelist/blacklist configured if needed
- [ ] `LOG_FORMAT=json` for structured logging
- [ ] Regular security audits via `doorman-trail.log`

### Development vs Production
| Feature | Development | Production |
|---------|-------------|------------|
| HTTPS Required | Optional | **Required** |
| CSRF Validation | Optional | **Enabled** |
| CORS | Permissive | **Strict** |
| Cookie Secure Flag | No | **Yes** |
| HSTS Header | No | **Yes** |
| Log Format | Plain | **JSON** |

## 📚 References

- **OWASP Top 10**: Addresses A01 (Broken Access Control), A02 (Cryptographic Failures), A05 (Security Misconfiguration)
- **CSP Level 3**: Content Security Policy implementation
- **RFC 6797**: HTTP Strict Transport Security (HSTS)
- **RFC 7519**: JSON Web Tokens (JWT)
- **CSRF Double Submit**: Industry-standard CSRF protection pattern

## 🔍 Testing

Security features are covered by comprehensive test suites:
- `tests/test_auth_csrf_https.py` - CSRF validation
- `tests/test_production_https_guard.py` - HTTPS enforcement
- `tests/test_ip_policy_allow_deny_cidr.py` - IP filtering
- `tests/test_security.py` - General security features
- `tests/test_request_id_and_logging_redaction.py` - Audit trail
- 323 total tests, all passing ✅

For questions or security concerns, please review the code or open an issue.
