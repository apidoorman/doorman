# Operations Guide (Abridged)

This guide covers production setup, deployment, monitoring, and runbooks.

## Production Environment

Key settings:

```bash
ENV=production
HTTPS_ONLY=true
MEM_OR_EXTERNAL=REDIS
JWT_SECRET_KEY=<strong-secret>
TOKEN_ENCRYPTION_KEY=<strong-secret>
MEM_ENCRYPTION_KEY=<strong-secret>
ALLOWED_ORIGINS=https://admin.yourdomain.com
CORS_STRICT=true
COOKIE_DOMAIN=yourdomain.com
LOG_FORMAT=json
```

## Deployment

- Single instance via Docker Compose
- Multi-instance requires Redis/Mongo and a load balancer
- Sticky sessions recommended (cookie auth)

## Health and Monitoring

- `/api/health` – liveness
- `/platform/monitor/readiness` – readiness (with manage_gateway perms)
- `/platform/monitor/metrics` – aggregated metrics (with manage_gateway perms)

## Reverse Proxy (Nginx Example)

Proxy pass to backend, forward `X-Forwarded-*` headers, and terminate TLS.

## Runbooks

- Clear caches: `DELETE /api/caches`
- Rotate API key: `POST /platform/credit/{group}/rotate`
- Restart gateway: `POST /platform/security/restart`

