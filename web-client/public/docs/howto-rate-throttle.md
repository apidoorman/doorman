# How‑to: Rate Limits & Throttling

Control traffic per user with rate limits (steady rate) and throttling (bursts).

## Rate Limits

Limit requests per window (e.g., 60/minute).

UI: Users → [username] → Rate Limit

Fields:

| Field | Meaning |
|-------|---------|
| rate_limit_duration | Max requests in a window |
| rate_limit_duration_type | Window unit (second/minute/hour/day) |

Example: 120 requests per minute → duration=120, type=minute.

## Throttling

Shape bursts with a sliding window and optional queue.

Fields:

| Field | Meaning |
|-------|---------|
| throttle_duration | Allowed in window (burst size) |
| throttle_duration_type | Window unit |
| throttle_wait_duration | Wait per excess request |
| throttle_wait_duration_type | Wait unit |
| throttle_queue_limit | Max queued/excess before 429 |

Example: allow 1 per second; additional requests wait 100ms each (up to 10 queued):

```json
{
  "throttle_duration": 1,
  "throttle_duration_type": "second",
  "throttle_wait_duration": 0.1,
  "throttle_wait_duration_type": "second",
  "throttle_queue_limit": 10
}
```

## Tips

- Use Monitor → Metrics to verify effects.
- Prefer user‑level settings for sensitive clients; use Tier rules for broad control.
- Return friendly 429s in clients and implement retries with backoff.

