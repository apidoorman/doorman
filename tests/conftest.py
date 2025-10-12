"""
Top-level pytest configuration for running tests against backend-services.

Sets required environment variables and exposes `client` and `authed_client`
fixtures backed by the FastAPI app in `backend-services/doorman.py`.
"""

import os
import sys
import asyncio

# TEST-ONLY credentials - DO NOT use these in production
os.environ.setdefault('MEM_OR_EXTERNAL', 'MEM')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
os.environ.setdefault('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
os.environ.setdefault('COOKIE_DOMAIN', 'testserver')
os.environ.setdefault('LOGIN_IP_RATE_LIMIT', '1000000')
os.environ.setdefault('LOGIN_IP_RATE_WINDOW', '60')

_HERE = os.path.dirname(__file__)
_BACKEND_DIR = os.path.abspath(os.path.join(_HERE, os.pardir, 'backend-services'))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    from doorman import doorman
    return AsyncClient(app=doorman, base_url='http://testserver')


@pytest_asyncio.fixture
async def authed_client():
    from doorman import doorman
    client = AsyncClient(app=doorman, base_url='http://testserver')

    r = await client.post(
        '/platform/authorization',
        json={'email': os.environ.get('DOORMAN_ADMIN_EMAIL'), 'password': os.environ.get('DOORMAN_ADMIN_PASSWORD')},
    )
    assert r.status_code == 200, r.text

    try:
        has_cookie = any(c.name == 'access_token_cookie' for c in client.cookies.jar)
        if not has_cookie:
            body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
            token = body.get('access_token')
            if token:
                client.cookies.set(
                    'access_token_cookie',
                    token,
                    domain=os.environ.get('COOKIE_DOMAIN') or 'testserver',
                    path='/',
                )
    except Exception:
        pass
    try:
        await client.put('/platform/user/admin', json={
            'bandwidth_limit_bytes': 0,
            'bandwidth_limit_window': 'day',
            'rate_limit_duration': 1000000,
            'rate_limit_duration_type': 'second',
            'throttle_duration': 1000000,
            'throttle_duration_type': 'second',
            'throttle_queue_limit': 1000000,
            'throttle_wait_duration': 0,
            'throttle_wait_duration_type': 'second'
        })
    except Exception:
        pass
    return client

# Test helpers for API/endpoint setup used by backend-services tests
async def create_api(client: AsyncClient, api_name: str, api_version: str):
    payload = {
        'api_name': api_name,
        'api_version': api_version,
        'api_description': f'{api_name} {api_version}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text
    return r

async def create_endpoint(client: AsyncClient, api_name: str, api_version: str, method: str, uri: str):
    payload = {
        'api_name': api_name,
        'api_version': api_version,
        'endpoint_method': method,
        'endpoint_uri': uri,
        'endpoint_description': f'{method} {uri}',
    }
    r = await client.post('/platform/endpoint', json=payload)
    assert r.status_code in (200, 201), r.text
    return r

async def subscribe_self(client: AsyncClient, api_name: str, api_version: str):
    r_me = await client.get('/platform/user/me')
    username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
    r = await client.post(
        '/platform/subscription/subscribe',
        json={'username': username, 'api_name': api_name, 'api_version': api_version},
    )
    assert r.status_code in (200, 201), r.text
    return r
