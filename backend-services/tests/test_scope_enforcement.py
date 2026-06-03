"""
Tests for OAuth2 scope-based authorization on gateway APIs.

Verifies:
- Requests with all required scopes are forwarded (no 403)
- Requests missing a required scope return 403 GTW018
- APIs with no required scopes are unaffected
- Anonymous users (no token) skip scope checks
- extract_token_scopes handles both `scope` string and `scp` list formats
"""

import pytest


# ---------------------------------------------------------------------------
# Unit tests: extract_token_scopes
# ---------------------------------------------------------------------------

def test_extract_token_scopes_space_separated():
    from utils.auth_util import extract_token_scopes
    payload = {'scope': 'read:customers write:orders'}
    assert extract_token_scopes(payload) == {'read:customers', 'write:orders'}


def test_extract_token_scopes_scp_list():
    from utils.auth_util import extract_token_scopes
    payload = {'scp': ['read:customers', 'write:orders']}
    assert extract_token_scopes(payload) == {'read:customers', 'write:orders'}


def test_extract_token_scopes_both_claims_merged():
    from utils.auth_util import extract_token_scopes
    payload = {'scope': 'read:customers', 'scp': ['write:orders', 'admin']}
    assert extract_token_scopes(payload) == {'read:customers', 'write:orders', 'admin'}


def test_extract_token_scopes_empty_payload():
    from utils.auth_util import extract_token_scopes
    assert extract_token_scopes({}) == set()


def test_extract_token_scopes_empty_scope_string():
    from utils.auth_util import extract_token_scopes
    payload = {'scope': '   '}
    assert extract_token_scopes(payload) == set()


def test_extract_token_scopes_scp_filters_non_strings():
    from utils.auth_util import extract_token_scopes
    payload = {'scp': ['valid', 42, None, 'also_valid']}
    assert extract_token_scopes(payload) == {'valid', 'also_valid'}


# ---------------------------------------------------------------------------
# Integration tests: scope enforcement on REST gateway
# ---------------------------------------------------------------------------

async def _create_scope_api(client, api_name: str, required_scopes: list[str]) -> dict:
    """Create an API with api_required_scopes set and register a GET /test endpoint."""
    r = await client.post('/platform/api', json={
        'api_name': api_name,
        'api_version': 'v1',
        'api_type': 'REST',
        'api_servers': ['http://localhost:19999'],
        'api_required_scopes': required_scopes,
        'api_allowed_groups': ['ALL'],
    })
    if r.status_code in (200, 201):
        # Register GET /test so the endpoint-existence check passes and the scope
        # check actually runs (without a registered endpoint, GTW003 fires first).
        await client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': 'v1',
            'endpoint_method': 'GET',
            'endpoint_uri': '/test',
            'endpoint_description': 'scope test endpoint',
        })
    return r


@pytest.mark.asyncio
async def test_scope_check_passes_with_matching_scopes(authed_client, monkeypatch):
    """Token with all required scopes should not get a 403."""
    from unittest.mock import AsyncMock, MagicMock, patch

    # Create API requiring 'read:data'
    r = await _create_scope_api(authed_client, 'scope-pass-api', ['read:data'])
    assert r.status_code in (200, 201), r.text

    # Patch the auth_required reference used inside gateway_routes
    import routes.gateway_routes as _gwr
    from utils import auth_util as _au

    original_auth = _au.auth_required

    async def _fake_auth(request):
        payload = await original_auth(request)
        payload['scope'] = 'read:data write:other'
        return payload

    monkeypatch.setattr(_gwr, 'auth_required', _fake_auth)

    with patch('services.gateway_service.httpx.AsyncClient') as mock_cls:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.content = b'ok'
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        r2 = await authed_client.get('/api/rest/scope-pass-api/v1/test')
        assert r2.status_code != 403, f'Expected non-403, got {r2.status_code}: {r2.text}'


@pytest.mark.asyncio
async def test_scope_check_fails_missing_scope(authed_client, monkeypatch):
    """Token missing a required scope should return 403 GTW018."""
    import routes.gateway_routes as _gwr
    from utils import auth_util as _au

    r = await _create_scope_api(authed_client, 'scope-fail-api', ['admin:write'])
    assert r.status_code in (200, 201), r.text

    original_auth = _au.auth_required

    async def _fake_auth_no_scope(request):
        payload = await original_auth(request)
        payload['scope'] = 'read:data'  # does NOT contain 'admin:write'
        return payload

    monkeypatch.setattr(_gwr, 'auth_required', _fake_auth_no_scope)

    r2 = await authed_client.get('/api/rest/scope-fail-api/v1/test')
    assert r2.status_code == 403, f'Expected 403, got {r2.status_code}: {r2.text}'
    body = r2.json()
    assert (body.get('error_code') or '').startswith('GTW018') or body.get('status_code') == 403


@pytest.mark.asyncio
async def test_scope_check_skipped_when_no_required_scopes(authed_client, monkeypatch):
    """API with empty api_required_scopes should never return 403 due to scopes."""
    import routes.gateway_routes as _gwr
    from utils import auth_util as _au

    r = await _create_scope_api(authed_client, 'scope-none-api', [])
    assert r.status_code in (200, 201), r.text

    original_auth = _au.auth_required

    async def _fake_auth_empty_scopes(request):
        payload = await original_auth(request)
        payload.pop('scope', None)
        payload.pop('scp', None)
        return payload

    monkeypatch.setattr(_gwr, 'auth_required', _fake_auth_empty_scopes)

    # With no required scopes, ANY token (even one with no scopes) passes
    r2 = await authed_client.get('/api/rest/scope-none-api/v1/test')
    assert r2.status_code != 403, f'Unexpected 403 for API with no required scopes'


@pytest.mark.asyncio
async def test_scope_check_skipped_for_public_api(authed_client):
    """Public APIs (api_public=True) bypass all auth including scope checks."""
    r = await authed_client.post('/platform/api', json={
        'api_name': 'scope-public-api',
        'api_version': 'v1',
        'api_type': 'REST',
        'api_servers': ['http://localhost:19999'],
        'api_public': True,
        'api_required_scopes': ['must:have'],
    })
    assert r.status_code in (200, 201), r.text

    from unittest.mock import AsyncMock, MagicMock, patch

    with patch('services.gateway_service.httpx.AsyncClient') as mock_cls:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.content = b'ok'
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        # Unauthenticated request to a public API should not 403 on scopes
        from httpx import AsyncClient
        from doorman import doorman
        async with AsyncClient(app=doorman, base_url='http://testserver') as anon:
            r2 = await anon.get('/api/rest/scope-public-api/v1/path')
            assert r2.status_code != 403, f'Public API should not scope-check, got {r2.status_code}'
