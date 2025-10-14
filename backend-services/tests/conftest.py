"""
Pytest configuration for backend-services tests.

Ensures the backend-services directory is on sys.path so imports like
`from utils...` resolve correctly when tests run from the repo root in CI.
"""

# External imports
import os
import sys

# TEST-ONLY credentials - DO NOT use these in production
os.environ.setdefault('MEM_OR_EXTERNAL', 'MEM')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
os.environ.setdefault('DOORMAN_ADMIN_PASSWORD', 'test-only-password-12chars')
os.environ.setdefault('COOKIE_DOMAIN', 'testserver')
os.environ.setdefault('LOGIN_IP_RATE_LIMIT', '1000000')
os.environ.setdefault('LOGIN_IP_RATE_WINDOW', '60')
os.environ.setdefault('LOGIN_IP_RATE_DISABLED', 'true')
os.environ.setdefault('DOORMAN_TEST_MODE', 'true')
os.environ.setdefault('ENABLE_HTTPX_CLIENT_CACHE', 'false')
os.environ.setdefault('DOORMAN_TEST_MODE', 'true')

# Compatibility toggles for Python 3.13 transport/middleware edge-cases
try:
    import sys as _sys
    if _sys.version_info >= (3, 13):
        # Avoid BaseHTTPMiddleware/receive wrapping issues on platform routes
        os.environ.setdefault('DISABLE_PLATFORM_CHUNKED_WRAP', 'true')
        # Use native Starlette behavior for CORS (disable ASGI shim)
        os.environ.setdefault('DISABLE_PLATFORM_CORS_ASGI', 'true')
        # Exclude problematic platform endpoint from body size middleware to
        # avoid EndOfStream/No response returned on some runtimes
        os.environ.setdefault('BODY_LIMIT_EXCLUDE_PATHS', '/platform/security/settings')
except Exception:
    pass

_HERE = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest_asyncio
from httpx import AsyncClient
import pytest
import asyncio
from typing import Optional
import datetime as _dt

try:
    from utils.database import database as _db
    _INITIAL_DB_SNAPSHOT: Optional[dict] = _db.db.dump_data() if getattr(_db, 'memory_only', True) else None
except Exception:
    _INITIAL_DB_SNAPSHOT = None

@pytest_asyncio.fixture(autouse=True)
async def ensure_memory_dump_defaults(monkeypatch, tmp_path):
    """Ensure sane defaults for memory dump/restore tests.

    - Force memory-only mode for safety in tests
    - Provide a default MEM_ENCRYPTION_KEY (tests can override or delete it)
    - Point MEM_DUMP_PATH at a per-test temporary directory and also update
      the imported module default if already loaded.
    """
    try:
        monkeypatch.setenv('MEM_OR_EXTERNAL', 'MEM')
        # Provide a stable, sufficiently long test key; individual tests may monkeypatch/delenv
        monkeypatch.setenv('MEM_ENCRYPTION_KEY', os.environ.get('MEM_ENCRYPTION_KEY') or 'test-encryption-key-32-characters-min')
        dump_base = tmp_path / 'mem' / 'memory_dump.bin'
        monkeypatch.setenv('MEM_DUMP_PATH', str(dump_base))
        # If memory_dump_util was already imported before env set, update its module-level default
        try:
            import utils.memory_dump_util as md
            md.DEFAULT_DUMP_PATH = str(dump_base)
        except Exception:
            pass
    except Exception:
        pass
    yield

# --- Per-test start/finish logging to pinpoint hangs ---
@pytest.fixture(autouse=True)
def _log_test_start_end(request):
    try:
        ts = _dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"=== [{ts}] START {request.node.nodeid}", flush=True)
    except Exception:
        pass
    yield
    try:
        ts = _dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"=== [{ts}] END   {request.node.nodeid}", flush=True)
    except Exception:
        pass

# Also log key env toggles at session start for reproducibility
@pytest.fixture(autouse=True, scope='session')
def _log_env_toggles():
    try:
        toggles = {
            'DISABLE_PLATFORM_CHUNKED_WRAP': os.getenv('DISABLE_PLATFORM_CHUNKED_WRAP'),
            'DISABLE_PLATFORM_CORS_ASGI': os.getenv('DISABLE_PLATFORM_CORS_ASGI'),
            'DISABLE_BODY_SIZE_LIMIT': os.getenv('DISABLE_BODY_SIZE_LIMIT'),
            'DOORMAN_TEST_MODE': os.getenv('DOORMAN_TEST_MODE'),
            'PYTHON_VERSION': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
        print(f"=== ENV TOGGLES: {toggles}", flush=True)
    except Exception:
        pass
    yield

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
                pwd = os.environ.get('DOORMAN_ADMIN_PASSWORD') or 'test-only-password-12chars'
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
