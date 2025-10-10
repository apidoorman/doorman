"""
Pytest configuration for backend-services tests.

Ensures the backend-services directory is on sys.path so imports like
`from utils...` resolve correctly when tests run from the repo root in CI.
"""

# External imports
import os
import sys

os.environ.setdefault('MEM_OR_EXTERNAL', 'MEM')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('STARTUP_ADMIN_EMAIL', 'admin@doorman.dev')
os.environ.setdefault('STARTUP_ADMIN_PASSWORD', 'password1')
os.environ.setdefault('COOKIE_DOMAIN', 'testserver')
os.environ.setdefault('LOGIN_IP_RATE_LIMIT', '1000000')
os.environ.setdefault('LOGIN_IP_RATE_WINDOW', '60')
os.environ.setdefault('LOGIN_IP_RATE_DISABLED', 'true')

_HERE = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest_asyncio
from httpx import AsyncClient
import pytest
import asyncio
from typing import Optional

try:
    from utils.database import database as _db
    _INITIAL_DB_SNAPSHOT: Optional[dict] = _db.db.dump_data() if getattr(_db, 'memory_only', True) else None
except Exception:
    _INITIAL_DB_SNAPSHOT = None

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

@pytest.fixture
def client():
    from doorman import doorman
    return AsyncClient(app=doorman, base_url='http://testserver')

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(autouse=True)
async def reset_http_client():
    """Reset the pooled httpx client between tests to prevent connection pool exhaustion."""
    # Reset before the test (important for tests that monkeypatch httpx.AsyncClient)
    try:
        from services.gateway_service import GatewayService
        await GatewayService.aclose_http_client()
    except Exception:
        pass

    # Reset rate limit counters before each test
    try:
        from utils.limit_throttle_util import reset_counters
        reset_counters()
    except Exception:
        pass

    yield
    # After each test, close and reset the pooled client
    try:
        from services.gateway_service import GatewayService
        await GatewayService.aclose_http_client()
    except Exception:
        pass

@pytest_asyncio.fixture(autouse=True, scope='module')
async def reset_in_memory_db_state():
    """Restore in-memory DB and caches before each test to ensure isolation.

    Prevents prior tests (e.g., password changes, user revocations, settings tweaks)
    from affecting later ones.
    """
    try:
        if _INITIAL_DB_SNAPSHOT is not None:
            from utils.database import database as _db
            _db.db.load_data(_INITIAL_DB_SNAPSHOT)
            try:
                from utils.database import user_collection
                from utils import password_util as _pw
                pwd = os.environ.get('STARTUP_ADMIN_PASSWORD') or 'password1'
                user_collection.update_one({'username': 'admin'}, {'$set': {'password': _pw.hash_password(pwd)}})
            except Exception:
                pass
    except Exception:
        pass
    try:
        from utils.doorman_cache_util import doorman_cache
        doorman_cache.clear_all()
    except Exception:
        pass
    yield

# Test helpers expected by some suites
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
