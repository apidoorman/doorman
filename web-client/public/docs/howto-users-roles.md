# How‑to: Manage Users & Roles (RBAC)

This guide shows how to create users, define roles (permissions), and control access.

## Concepts

- Users: human or service identities that authenticate to the gateway.
- Roles: permission sets (e.g., manage_apis, view_logs, manage_security).
- Groups: used together with roles to authorize access to specific APIs.

## Create a Role

1. Go to Roles → Add
2. Name the role (e.g., "operator") and select permissions needed
   - Example minimal operator: `view_logs`, `view_analytics`
3. Save

API example:
```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/role" -d '{
    "role_name": "operator",
    "role_description": "Read-only operations",
    "view_logs": true,
    "view_analytics": true
  }'
```

## Create a User

1. Go to Users → Add
2. Fill identity and choose a role
3. Enable UI access (for console access) if needed
4. Save

API example:
```bash
curl -b $COOKIE -H 'Content-Type: application/json' -X POST \
  "$BASE/platform/user" -d '{
    "username": "jane",
    "email": "jane@example.com",
    "password": "StrongPassword!234",
    "role": "operator",
    "ui_access": true
  }'
```

## Groups and API Access

Groups are attached to APIs (allowed_groups) and to users (via group membership). Access is granted when a user’s groups intersect an API’s allowed groups and they’re subscribed to the API.

Typical pattern:

1. Create a group (e.g., "sales")
2. Attach group to API (API → Allowed Groups)
3. Add user to the group (User → Groups)
4. Subscribe user to API

## Best Practices

- Keep the `admin` role for platform administrators only.
- Create dedicated roles for teams: operators (read), integrators (manage_apis), auditors (view_logs).
- Use Groups to partition API access by domain (e.g., finance, sales, internal).

