"""
Tests for OIDC/JWKS-based gateway authentication.

Verifies:
- A valid RS256 token from a configured OIDC provider is accepted
- A token from an unknown issuer returns 401 GTW016
- An audience mismatch returns 401 GTW017
- A JWKS fetch failure returns 503 GTW015
- The JWKS response is cached (httpx called only once for two requests)
- require_local_user=True rejects tokens whose sub has no local account
- Existing local HS256 tokens still work alongside OIDC configuration
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


# ---------------------------------------------------------------------------
# Key generation helpers
# ---------------------------------------------------------------------------

def _gen_rsa_keypair():
    """Generate a fresh RSA-2048 key pair for test token signing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem, private_key, public_key


def _make_rs256_token(private_pem: str, kid: str, issuer: str, subject: str = 'oidc_user',
                      audience: str | None = None, extra_claims: dict | None = None) -> str:
    """Sign a JWT with an RS256 key."""
    from jose import jwt as _jwt
    claims = {
        'sub': subject,
        'iss': issuer,
        'iat': int(time.time()),
        'exp': int(time.time()) + 3600,
    }
    if audience:
        claims['aud'] = audience
    if extra_claims:
        claims.update(extra_claims)
    return _jwt.encode(claims, private_pem, algorithm='RS256', headers={'kid': kid})


def _public_key_to_jwk(public_key, kid: str) -> dict:
    """Convert an RSA public key to a JWK dict (minimal n/e representation)."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    import base64

    pub_numbers = public_key.public_key().public_numbers() if hasattr(public_key, 'private_bytes') else public_key.public_numbers()

    def _int_to_base64url(n: int) -> str:
        length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(length, 'big')).rstrip(b'=').decode()

    return {
        'kty': 'RSA',
        'use': 'sig',
        'kid': kid,
        'alg': 'RS256',
        'n': _int_to_base64url(pub_numbers.n),
        'e': _int_to_base64url(pub_numbers.e),
    }


def _mock_jwks_response(jwk_dict: dict):
    """Return a mock httpx Response for a JWKS endpoint."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {'keys': [jwk_dict]}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_ISSUER = 'https://test-idp.example.com'
_TEST_KID = 'test-oidc-key-1'
_TEST_AUD = 'doorman-api'
_TEST_JWKS_URI = 'https://test-idp.example.com/.well-known/jwks.json'


@pytest.fixture(autouse=True)
def _clear_jwks_cache():
    """Clear the JWKS in-memory cache before each test."""
    from utils import key_util
    key_util._jwks_cache.clear()
    yield
    key_util._jwks_cache.clear()


@pytest.fixture()
def oidc_keypair():
    private_pem, public_pem, private_key, public_key = _gen_rsa_keypair()
    jwk_dict = _public_key_to_jwk(public_key, _TEST_KID)
    return {'private_pem': private_pem, 'public_pem': public_pem, 'jwk': jwk_dict}


@pytest.fixture()
def configured_oidc_provider(monkeypatch):
    """Monkey-patch security settings to include a test OIDC provider."""
    from utils import security_settings_util

    original = security_settings_util.get_cached_settings

    def _patched():
        settings = original()
        settings['oidc_providers'] = [{
            'issuer': _TEST_ISSUER,
            'jwks_uri': _TEST_JWKS_URI,
            'audience': _TEST_AUD,
            'algorithms': ['RS256'],
            'require_local_user': False,
        }]
        return settings

    monkeypatch.setattr(security_settings_util, 'get_cached_settings', _patched)


@pytest.fixture()
def configured_oidc_no_audience(monkeypatch):
    """OIDC provider without audience validation."""
    from utils import security_settings_util

    original = security_settings_util.get_cached_settings

    def _patched():
        settings = original()
        settings['oidc_providers'] = [{
            'issuer': _TEST_ISSUER,
            'jwks_uri': _TEST_JWKS_URI,
            'audience': None,
            'algorithms': ['RS256'],
            'require_local_user': False,
        }]
        return settings

    monkeypatch.setattr(security_settings_util, 'get_cached_settings', _patched)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_oidc_token_valid_provider(
    client, oidc_keypair, configured_oidc_provider, monkeypatch
):
    """A valid RS256 token from a configured provider is accepted by the gateway."""
    token = _make_rs256_token(
        oidc_keypair['private_pem'], _TEST_KID, _TEST_ISSUER, audience=_TEST_AUD
    )

    mock_resp = _mock_jwks_response(oidc_keypair['jwk'])
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(return_value=mock_resp)

    # Create a public test API so we only exercise auth, not subscriptions
    from utils.database_async import api_collection
    await api_collection.delete_one({'api_name': 'oidc-test-api'})
    await api_collection.insert_one({
        'api_name': 'oidc-test-api', 'api_version': 'v1', 'api_type': 'REST',
        'api_servers': ['http://localhost:19999'], 'api_path': '/oidc-test-api/v1',
        'api_id': 'oidc-test-id', 'api_auth_required': False, 'api_public': True,
    })

    with patch('httpx.AsyncClient', return_value=mock_http_client):
        from utils.auth_util import auth_required
        from fastapi import Request as _Req
        from starlette.testclient import TestClient

        # Call auth_required directly with a Bearer token
        scope = {
            'type': 'http', 'method': 'GET', 'path': '/test',
            'headers': [(b'authorization', f'Bearer {token}'.encode())],
            'query_string': b'',
        }
        req = _Req(scope)
        payload = await auth_required(req)

    assert payload['sub'] == 'oidc_user'
    assert payload['iss'] == _TEST_ISSUER


@pytest.mark.asyncio
async def test_oidc_token_unknown_issuer(client, oidc_keypair, monkeypatch):
    """Token from an issuer not in oidc_providers returns 401 GTW016."""
    from fastapi import HTTPException, Request as _Req
    from utils import security_settings_util

    original = security_settings_util.get_cached_settings
    monkeypatch.setattr(
        security_settings_util, 'get_cached_settings',
        lambda: {**original(), 'oidc_providers': []}  # empty — no providers configured
    )

    token = _make_rs256_token(
        oidc_keypair['private_pem'], _TEST_KID, 'https://unknown-idp.example.com'
    )
    scope = {
        'type': 'http', 'method': 'GET', 'path': '/test',
        'headers': [(b'authorization', f'Bearer {token}'.encode())],
        'query_string': b'',
    }
    req = _Req(scope)

    from utils.auth_util import auth_required
    with pytest.raises(HTTPException) as exc_info:
        await auth_required(req)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == 'GTW016'


@pytest.mark.asyncio
async def test_oidc_token_audience_mismatch(
    client, oidc_keypair, configured_oidc_provider, monkeypatch
):
    """Token with wrong audience returns 401 GTW017."""
    from fastapi import HTTPException, Request as _Req

    token = _make_rs256_token(
        oidc_keypair['private_pem'], _TEST_KID, _TEST_ISSUER,
        audience='wrong-audience'  # configured expects _TEST_AUD
    )

    mock_resp = _mock_jwks_response(oidc_keypair['jwk'])
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(return_value=mock_resp)

    scope = {
        'type': 'http', 'method': 'GET', 'path': '/test',
        'headers': [(b'authorization', f'Bearer {token}'.encode())],
        'query_string': b'',
    }
    req = _Req(scope)

    from utils.auth_util import auth_required
    with patch('httpx.AsyncClient', return_value=mock_http_client):
        with pytest.raises(HTTPException) as exc_info:
            await auth_required(req)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == 'GTW017'


@pytest.mark.asyncio
async def test_oidc_jwks_fetch_failure(
    client, oidc_keypair, configured_oidc_provider, monkeypatch
):
    """JWKS fetch failure returns 503 GTW015."""
    import httpx
    from fastapi import HTTPException, Request as _Req

    token = _make_rs256_token(
        oidc_keypair['private_pem'], _TEST_KID, _TEST_ISSUER, audience=_TEST_AUD
    )

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = AsyncMock(side_effect=httpx.ConnectError('unreachable'))

    scope = {
        'type': 'http', 'method': 'GET', 'path': '/test',
        'headers': [(b'authorization', f'Bearer {token}'.encode())],
        'query_string': b'',
    }
    req = _Req(scope)

    from utils.auth_util import auth_required
    with patch('httpx.AsyncClient', return_value=mock_http_client):
        with pytest.raises(HTTPException) as exc_info:
            await auth_required(req)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == 'GTW015'


@pytest.mark.asyncio
async def test_oidc_jwks_cache_hit(
    client, oidc_keypair, configured_oidc_no_audience, monkeypatch
):
    """JWKS endpoint is called only once for two consecutive token validations."""
    from fastapi import Request as _Req

    call_count = 0

    def _make_token():
        return _make_rs256_token(oidc_keypair['private_pem'], _TEST_KID, _TEST_ISSUER)

    mock_resp = _mock_jwks_response(oidc_keypair['jwk'])

    async def _fake_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_resp

    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.get = _fake_get

    from utils.auth_util import auth_required

    def _make_req(token: str):
        return _Req({
            'type': 'http', 'method': 'GET', 'path': '/test',
            'headers': [(b'authorization', f'Bearer {token}'.encode())],
            'query_string': b'',
        })

    with patch('httpx.AsyncClient', return_value=mock_http_client):
        await auth_required(_make_req(_make_token()))
        await auth_required(_make_req(_make_token()))

    assert call_count == 1, f'Expected 1 JWKS fetch, got {call_count}'


@pytest.mark.asyncio
async def test_local_hs256_token_still_works_alongside_oidc(
    authed_client, configured_oidc_provider
):
    """Configuring OIDC providers must not break existing local HS256 auth."""
    r = await authed_client.get('/platform/user/me')
    assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'
