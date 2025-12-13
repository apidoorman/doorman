# How‑to: Credits & Quotas

Use credit groups to track and enforce usage, and inject API keys.

## Create a Credit Group

Contains default API key and tiers (quotas).

```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit" -d '{
    "api_credit_group": "demo-api",
    "api_key": "demo-secret-key-123",
    "api_key_header": "x-api-key",
    "credit_tiers": [
      {"tier_name": "default", "credits": 100000, "reset_frequency": "monthly"}
    ]
  }'
```

## Enable Credits on an API

```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/api" -d '{
    "api_name": "demo",
    "api_version": "v1",
    "api_servers": ["http://httpbin.org"],
    "api_type": "REST",
    "api_credits_enabled": true,
    "api_credit_group": "demo-api"
  }'
```

## User‑Specific Overrides

Assign a personal API key and tier to a user.

```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/credit/alice" -d '{
    "api_credit_group": "demo-api",
    "api_key": "ALICE-KEY-XYZ",
    "api_key_header": "x-api-key",
    "credit_tiers": [{"tier_name": "premium", "credits": 500000, "reset_frequency": "monthly"}]
  }'
```

## Notes

- Input/output accounting can be configured per endpoint type.
- When credits deplete, calls fail with an error until the next reset.
- Use Analytics and Logs to monitor consumption.

