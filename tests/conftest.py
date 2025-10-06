"""
Top-level pytest configuration for running tests against backend-services.

Sets required environment variables and exposes `client` and `authed_client`
fixtures backed by the FastAPI app in `backend-services/doorman.py`.
"""

import os
import sys
import asyncio

os.environ.setdefault('MEM_OR_EXTERNAL', 'MEM')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('STARTUP_ADMIN_EMAIL', 'admin@doorman.dev')
os.environ.setdefault('STARTUP_ADMIN_PASSWORD', 'password1')
os.environ.setdefault('COOKIE_DOMAIN', 'testserver')

# Ensure backend-services is on sys.path for imports like `from doorman import doorman`
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
        json={'email': os.environ.get('STARTUP_ADMIN_EMAIL'), 'password': os.environ.get('STARTUP_ADMIN_PASSWORD')},
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

