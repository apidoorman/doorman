# v1 Launch Fixes

This file tracks potential issues, impact, and suggested fixes discovered during the pre-launch review.

## Auth/session + UI access
- Cookie SameSite handling: `COOKIE_SAMESITE=None` on HTTP drops cookies in browsers. Fix: in `backend-services/routes/authorization_routes.py`, if `samesite == 'none'` and `_secure` is false, downgrade to `lax` and log a warning. This prevents confusing login loops in dev.




- Admin UI access inconsistency: login allows “super admin” regardless of `ui_access`, but `AuthContext` later sets `hasUIAccess` strictly from `user.ui_access`. Fix: align `AuthContext` to treat `role === 'admin'` or `username === 'admin'` as UI‑allowed (or ensure seed/restore always forces `ui_access=true`).




## Admin/user/role management
- `GET /platform/user/email/{email}` can 500 when user not found: `UserService.get_user_by_email` dereferences `user` before checking `None`. Fix: check `if not user` before accessing keys.
- Admin subscription bypass is broken: `subscription_required` compares `username` to `DOORMAN_ADMIN_EMAIL`, so admin users don’t bypass subscriptions unless username equals email. Fix: use `is_admin_user(username)` or `username == 'admin'` (or check role).
- Response schema mismatch: `GET /platform/user/email/{email}` declares `response_model=list[UserModelResponse]` but returns a single user object. Fix: adjust response_model or return list consistently.
- Super admin cannot see self: `/platform/user/all`, `/platform/user/{username}`, and `/platform/user/email/{email}` always hide `admin`. Fix: allow `admin` to see self when the requester is admin (or when `username == auth_username`).

## Gateway routing + subscriptions
- Subscriptions allow horizontal privilege escalation: `/platform/subscription/subscribe` and `/platform/subscription/unsubscribe` allow any authenticated user to target any username; only group membership is checked. Fix: if `api_data.username != actor`, require `manage_subscriptions` (or admin) before proceeding.
- Subscription reads lack permission checks: `/platform/subscription/subscriptions/{user_id}` returns any user’s subscriptions to any authenticated caller. Fix: restrict to self or require `manage_subscriptions`.
- API allowed roles are defined but never enforced on gateway requests. If roles are intended to gate API access, add a role check alongside group/subscription enforcement; otherwise clarify docs/UI to avoid false expectations.

## Analytics/logs/dashboard + config/security
- Config export APIs use `cursor.to_list()` on sync PyMongo cursors (`backend-services/routes/config_routes.py`). In Mongo mode this raises `AttributeError`. Fix: replace with `list(cursor)` or use async db helpers consistently.
- Subscriptions available-apis uses `cursor.to_list()` on sync cursor (`backend-services/routes/subscription_routes.py`); same issue in Mongo mode. Fix: convert to list like above or use async helper.
- Dashboard data requires only auth, not `view_analytics`. If analytics visibility is supposed to be permissioned, add a role check (or clarify that dashboard is always visible to UI‑access users).

## Tests/smoke coverage
- No coverage for subscription permission checks (subscribe/unsubscribe another user, read others’ subscriptions). Add tests to prevent privilege escalation regressions.
- No coverage for API role enforcement on gateway access (if intended). Add a test that denies a user whose role is not in `api_allowed_roles`.
- No coverage for cookie SameSite/Secure behavior in HTTP dev. Add a web client smoke test or integration test that validates cookie presence after login when `HTTPS_ONLY=false`.
- Config export/import is only exercised in memory mode; no test for Mongo mode cursor handling. Add a small integration test or adjust code to use driver‑agnostic helper.
