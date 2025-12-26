import os
import sys
import time
import asyncio

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client import LiveClient
from config import ADMIN_EMAIL, ADMIN_PASSWORD, BASE_URL, STRICT_HEALTH, require_env

# Ensure live tests talk to the running gateway, not an in-process app
os.environ.setdefault('DOORMAN_RUN_LIVE', '1')
# Default feature toggles enabled for live runs
os.environ.setdefault('DOORMAN_TEST_GRPC', '1')
os.environ.setdefault('DOORMAN_TEST_GRAPHQL', '1')

# Enable teardown cleanup by default, unless explicitly disabled by env.
if os.getenv('DOORMAN_TEST_CLEANUP') is None:
    os.environ['DOORMAN_TEST_CLEANUP'] = 'true'

@pytest.fixture(scope='session')
def base_url() -> str:
    require_env()
    return BASE_URL


@pytest.fixture(scope='session')
def client(base_url) -> LiveClient:
    c = LiveClient(base_url)
    deadline = time.time() + 30
    last_err = None
    while time.time() < deadline:
        try:
            r = c.get('/api/health')
            if r.status_code == 200:
                if STRICT_HEALTH:
                    try:
                        j = r.json()
                        data = j.get('response') if isinstance(j, dict) else None
                        if not isinstance(data, dict):
                            data = j if isinstance(j, dict) else {}
                        ok = data.get('status') in ('online', 'healthy')
                        if ok:
                            break
                        last_err = f'status json={j}'
                    except Exception as e:
                        last_err = f'json parse error: {e}'
                else:
                    break
            last_err = f'status={r.status_code} body={r.text}'
        except Exception as e:
            last_err = str(e)
        time.sleep(1)
    else:
        pytest.fail(f'Doorman backend not healthy at {base_url}/api/health: {last_err}')

    auth = c.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert 'access_token' in auth.get('response', auth), 'login did not return access_token'
    try:
        yield c
    finally:
        # Always perform session-level cleanup of created resources to leave the system pristine
        try:
            c.cleanup()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def ensure_session_and_relaxed_limits(client: LiveClient):
    """Per-test guard: ensure we're authenticated and not rate-limited.

    - Re-login if session is invalid (status not 200/204).
    - Clear caches and set very generous admin rate/throttle to avoid cross-test 429s.
    """
    try:
        r = client.get('/platform/authorization/status')
        if r.status_code not in (200, 204):
            from config import ADMIN_EMAIL, ADMIN_PASSWORD

            client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    except Exception:
        from config import ADMIN_EMAIL, ADMIN_PASSWORD

        client.login(ADMIN_EMAIL, ADMIN_PASSWORD)

    # Remove any tier assignments that might have strict rate limits
    for _ in range(3):
        try:
            client.delete('/platform/tiers/assignments/admin')
            break
        except Exception:
            pass

    # Clear caches first to reset any rate limit state
    for _ in range(3):  # Retry in case of transient rate limit
        try:
            client.delete('/api/caches')
            break
        except Exception:
            import time
            time.sleep(0.1)

    # Set generous rate limits
    for _ in range(3):
        try:
            r = client.put(
                '/platform/user/admin',
                json={
                    'rate_limit_duration': 1000000,
                    'rate_limit_duration_type': 'second',
                    'throttle_duration': 1000000,
                    'throttle_duration_type': 'second',
                    'throttle_queue_limit': 1000000,
                    'throttle_wait_duration': 0,
                    'throttle_wait_duration_type': 'second',
                },
            )
            if r.status_code in (200, 201):
                break
        except Exception:
            import time
            time.sleep(0.1)


def pytest_addoption(parser):
    parser.addoption('--graph', action='store_true', default=False, help='Force GraphQL tests')
    parser.addoption('--grpc', action='store_true', default=False, help='Force gRPC tests')


# ---------------------------------------------
# Async adapter + helpers expected by some tests
# ---------------------------------------------

class _AsyncLiveClientAdapter:
    """Minimal async wrapper around LiveClient (requests.Session based).

    Provides async get/post/put/delete/options methods compatible with tests that
    use `await authed_client.<verb>(...)`. Internally delegates to the sync client
    on a thread via asyncio.to_thread to avoid blocking the event loop.
    """

    def __init__(self, sync_client: LiveClient) -> None:
        self._c = sync_client

    async def get(self, path: str, **kwargs):
        return await asyncio.to_thread(self._c.get, path, **kwargs)

    async def post(self, path: str, **kwargs):
        return await asyncio.to_thread(self._c.post, path, **kwargs)

    async def put(self, path: str, **kwargs):
        return await asyncio.to_thread(self._c.put, path, **kwargs)

    async def delete(self, path: str, **kwargs):
        return await asyncio.to_thread(self._c.delete, path, **kwargs)

    async def options(self, path: str, **kwargs):
        return await asyncio.to_thread(self._c.options, path, **kwargs)


@pytest_asyncio.fixture
async def authed_client(client: LiveClient):
    """Async wrapper around the live server client.

    Live tests must exercise the running gateway process; avoid in-process app clients.
    """
    return _AsyncLiveClientAdapter(client)


@pytest_asyncio.fixture
async def live_authed_client(client: LiveClient):
    """Out-of-process async client fixture for true live server tests.

    Wraps the session-authenticated LiveClient and exposes async HTTP verbs.
    Use this for tests that need to hit an actual running server.
    """
    return _AsyncLiveClientAdapter(client)


# Helper coroutines referenced by some live tests
async def create_api(authed_client: _AsyncLiveClientAdapter, name: str, ver: str):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        # Default REST upstream placeholder (tests usually monkeypatch httpx/grpc)
        'api_servers': ['http://up.example'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    await authed_client.post('/platform/api', json=payload)


async def create_endpoint(
    authed_client: _AsyncLiveClientAdapter, name: str, ver: str, method: str, uri: str
):
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': method,
            'endpoint_uri': uri,
            'endpoint_description': f'{method} {uri}',
        },
    )


async def subscribe_self(authed_client: _AsyncLiveClientAdapter, name: str, ver: str):
    await authed_client.post(
        '/platform/subscription/subscribe',
        json={'api_name': name, 'api_version': ver, 'username': 'admin'},
    )
