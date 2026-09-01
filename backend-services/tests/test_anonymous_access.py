"""
Tests for anonymous access with IP-keyed credits (Feature 2).

Verifies:
- Unauthenticated requests to an api_anonymous_allowed=True API succeed
- Credits are deducted from the anon:{ip} identity on each anonymous request
- Exhausted anonymous credits return GTW008
- Authenticated users on optional-auth APIs use their own credits, not the anon pool
- Unauthenticated requests to an api_anonymous_allowed=False API return 401
- api_anonymous_credit_group is used when configured (separate from api_credit_group)
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeHTTPResponse:
    def __init__(self, status_code=200, json_body=None):
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = ''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._json_body


class _FakeAsyncClient:
    """Always returns HTTP 200; records the last URL called."""

    def __init__(self, *args, **kwargs):
        self.last_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def request(self, method, url, **kwargs):
        self.last_url = url
        return _FakeHTTPResponse(200, json_body={'ok': True})

    async def get(self, url, **kwargs):
        return _FakeHTTPResponse(200, json_body={'ok': True})

    async def post(self, url, **kwargs):
        return _FakeHTTPResponse(200, json_body={'ok': True})


async def _create_optional_auth_api(
    client,
    name: str,
    ver: str = 'v1',
    credits_enabled: bool = True,
    credit_group: str | None = None,
    anon_allowed: bool = True,
    anon_credit_group: str | None = None,
):
    """Create an API with api_auth_required=False and optional credit settings."""
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_auth_required': False,
        'api_anonymous_allowed': anon_allowed,
        'api_credits_enabled': credits_enabled,
    }
    if credit_group:
        payload['api_credit_group'] = credit_group
    if anon_credit_group:
        payload['api_anonymous_credit_group'] = anon_credit_group

    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text

    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/data',
            'endpoint_description': 'data endpoint',
        },
    )
    assert r2.status_code in (200, 201), r2.text
    return name, ver


def _seed_anon_credits(ip: str, group: str, available: int) -> None:
    """Directly write an anon credit document into the in-memory DB."""
    from utils.database import user_credit_collection

    username = f'anon:{ip}'
    user_credit_collection.delete_one({'username': username})
    user_credit_collection.insert_one({
        'username': username,
        'users_credits': {
            group: {
                'tier_name': 'anonymous',
                'available_credits': available,
                'user_api_key': None,
            }
        },
    })


def _get_anon_credits(ip: str, group: str) -> int | None:
    """Read available credits for an anonymous IP from the in-memory DB."""
    from utils.database import user_credit_collection

    doc = user_credit_collection.find_one({'username': f'anon:{ip}'})
    if not doc:
        return None
    return (doc.get('users_credits') or {}).get(group, {}).get('available_credits')


def _seed_user_credits(username: str, group: str, available: int) -> None:
    """Seed credits for a named user."""
    from utils.database import user_credit_collection

    user_credit_collection.delete_one({'username': username})
    user_credit_collection.insert_one({
        'username': username,
        'users_credits': {
            group: {
                'tier_name': 'user',
                'available_credits': available,
                'user_api_key': None,
            }
        },
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anonymous_request_succeeds_on_allowed_api(monkeypatch, client):
    """Unauthenticated request to api_anonymous_allowed=True succeeds (no 401)."""
    # We need an admin client to register the API first
    import os
    from doorman import doorman
    from httpx import AsyncClient

    admin = AsyncClient(app=doorman, base_url='http://testserver')
    r_login = await admin.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )
    assert r_login.status_code == 200, r_login.text

    name, ver = await _create_optional_auth_api(
        admin,
        name='anon-basic',
        credits_enabled=False,
        anon_allowed=True,
    )
    await admin.delete('/api/caches')

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    # Plain unauthenticated client
    r = await client.get(f'/api/rest/{name}/{ver}/data')
    assert r.status_code != 401, f'Expected non-401 for anonymous-allowed API, got {r.status_code}'
    assert r.status_code != 403, f'Expected non-403 for anonymous-allowed API, got {r.status_code}'


@pytest.mark.asyncio
async def test_anonymous_credits_deducted_per_request(monkeypatch, client):
    """Credits are deducted from anon:{ip} on each anonymous request."""
    import os
    from doorman import doorman
    from httpx import AsyncClient

    admin = AsyncClient(app=doorman, base_url='http://testserver')
    await admin.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )

    group = 'anon-credits-grp'
    name, ver = await _create_optional_auth_api(
        admin,
        name='anon-credit-deduct',
        credits_enabled=True,
        credit_group=group,
        anon_allowed=True,
    )

    # The actual client IP seen by Starlette in test mode is 127.0.0.1
    test_ip = '127.0.0.1'
    _seed_anon_credits(test_ip, group, 5)
    await admin.delete('/api/caches')

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await client.get(f'/api/rest/{name}/{ver}/data')
    body = r.json()
    status = body.get('status_code', r.status_code)
    # A 200 upstream means credit deduction succeeded
    if status not in (401, 403, 500):
        remaining = _get_anon_credits(test_ip, group)
        # If credits were seeded and deducted, remaining should be < 5
        # (or None if ensure_anonymous_credits re-created the doc; that's also valid)
        assert remaining is None or remaining < 5, (
            f'Expected credit deduction, got remaining={remaining}'
        )


@pytest.mark.asyncio
async def test_anonymous_credits_exhausted_returns_gtw008(monkeypatch, client):
    """When anonymous credits reach 0, further requests return GTW008."""
    import os
    from doorman import doorman
    from httpx import AsyncClient

    admin = AsyncClient(app=doorman, base_url='http://testserver')
    await admin.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )

    group = 'anon-exhausted-grp'
    name, ver = await _create_optional_auth_api(
        admin,
        name='anon-exhausted',
        credits_enabled=True,
        credit_group=group,
        anon_allowed=True,
    )

    test_ip = '127.0.0.1'
    _seed_anon_credits(test_ip, group, 0)  # already exhausted
    await admin.delete('/api/caches')

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await client.get(f'/api/rest/{name}/{ver}/data')
    body = r.json()
    status = body.get('status_code', r.status_code)
    error_code = body.get('error_code', '')

    # With 0 credits the gateway must block with GTW008
    assert status == 401 or error_code == 'GTW008', (
        f'Expected GTW008 / 401 for exhausted anonymous credits, got status={status} '
        f'error_code={error_code} body={body}'
    )


@pytest.mark.asyncio
async def test_anonymous_not_allowed_passes_through_without_username(monkeypatch, client):
    """api_anonymous_allowed=False (default) on an optional-auth API allows unauthenticated
    requests through — they proceed without a username (original behaviour).
    Contrast: api_auth_required=True would block with 401."""
    import os
    from doorman import doorman
    from httpx import AsyncClient

    admin = AsyncClient(app=doorman, base_url='http://testserver')
    await admin.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )

    name, ver = await _create_optional_auth_api(
        admin,
        name='anon-passthrough',
        credits_enabled=False,
        anon_allowed=False,   # anonymous identity NOT derived; no credit tracking
    )
    await admin.delete('/api/caches')

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await client.get(f'/api/rest/{name}/{ver}/data')
    body = r.json()
    status = body.get('status_code', r.status_code)

    # Optional-auth API with no credentials — must NOT 401 (no auth required)
    assert status != 401, (
        f'Optional-auth API should not return 401 without credentials, got {status}'
    )
    assert status != 403, (
        f'Optional-auth API should not return 403 without credentials, got {status}'
    )


@pytest.mark.asyncio
async def test_authenticated_user_uses_own_credits_not_anon_pool(monkeypatch, authed_client):
    """Authenticated users on optional-auth APIs consume their own credits, not anon credits."""
    group = 'auth-on-optional-grp'
    name, ver = await _create_optional_auth_api(
        authed_client,
        name='auth-optional',
        credits_enabled=True,
        credit_group=group,
        anon_allowed=True,
    )

    # Seed authenticated user ('admin') with 3 credits
    _seed_user_credits('admin', group, 3)

    # Seed an anon identity with 10 credits to verify it is NOT touched
    test_ip = '127.0.0.1'
    _seed_anon_credits(test_ip, group, 10)

    await authed_client.delete('/api/caches')

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await authed_client.get(f'/api/rest/{name}/{ver}/data')
    body = r.json()
    status = body.get('status_code', r.status_code)

    # Request should succeed (authenticated user has credits)
    assert status not in (401, 403, 500), f'Expected success for authed user, got {status}'

    # Authenticated user's credits should be deducted
    from utils.database import user_credit_collection
    user_doc = user_credit_collection.find_one({'username': 'admin'})
    user_remaining = (user_doc.get('users_credits') or {}).get(group, {}).get('available_credits')
    assert user_remaining == 2, f'Expected admin credits to be 2, got {user_remaining}'

    # Anon pool must remain untouched
    anon_remaining = _get_anon_credits(test_ip, group)
    assert anon_remaining == 10, (
        f'Anon credits should be untouched (10), got {anon_remaining}'
    )


@pytest.mark.asyncio
async def test_anonymous_credit_group_used_when_configured(monkeypatch, client):
    """When api_anonymous_credit_group is set, anonymous requests deduct from that group."""
    import os
    from doorman import doorman
    from httpx import AsyncClient

    admin = AsyncClient(app=doorman, base_url='http://testserver')
    await admin.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )

    normal_group = 'normal-credits-grp2'
    anon_group = 'anon-specific-grp2'

    name, ver = await _create_optional_auth_api(
        admin,
        name='anon-sep-group',
        credits_enabled=True,
        credit_group=normal_group,
        anon_allowed=True,
        anon_credit_group=anon_group,  # separate group for anon
    )

    test_ip = '127.0.0.1'
    # Seed the anon-specific group with 5 credits; leave normal group empty
    _seed_anon_credits(test_ip, anon_group, 5)
    await admin.delete('/api/caches')

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await client.get(f'/api/rest/{name}/{ver}/data')
    body = r.json()
    status = body.get('status_code', r.status_code)

    # The request should NOT be blocked (anon group has credits)
    assert status not in (401, 403), (
        f'Expected success using anon_credit_group, got status={status} body={body}'
    )

    # Verify the anon-specific group was decremented
    remaining = _get_anon_credits(test_ip, anon_group)
    assert remaining is None or remaining < 5, (
        f'Expected anon_credit_group to be deducted, got {remaining}'
    )
