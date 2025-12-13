# Doorman Gateway Guides

This section contains practical, task‑oriented guides for operating the gateway.

## What do you want to do?

- Manage access with Users & Roles → [/docs/howto-users-roles.md](/docs/howto-users-roles.md)
- Publish a REST API → [/docs/howto-create-api-rest.md](/docs/howto-create-api-rest.md)
- Control Rate Limits & Throttling → [/docs/howto-rate-throttle.md](/docs/howto-rate-throttle.md)
- Set up Credits & Quotas → [/docs/howto-credits-quotas.md](/docs/howto-credits-quotas.md)
- Troubleshoot requests → [/docs/troubleshooting.md](/docs/troubleshooting.md)
- Explore UI fields → [/docs/using-fields.html](/docs/using-fields.html)

## Quick tips

- Prefer explicit, least‑privilege roles; grant only the permissions required.
- For API access, use Groups + Subscriptions to control “who can call what”.
- Start with generous rate limits in dev; tighten in production with metrics.
- Avoid wildcard origins in CORS when credentials are used.
- Use the CORS checker and monitor endpoints to validate configuration.

