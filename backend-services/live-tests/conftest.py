import os
import time
import pytest
import requests

from config import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD, require_env, STRICT_HEALTH
from client import LiveClient


@pytest.fixture(scope='session')
def base_url() -> str:
    require_env()
    return BASE_URL


@pytest.fixture(scope='session')
def client(base_url) -> LiveClient:
    c = LiveClient(base_url)
    # Wait for backend health
    deadline = time.time() + 30
    last_err = None
    while time.time() < deadline:
        try:
            r = c.get('/api/status')
            if r.status_code == 200:
                # Optional strict health gate: require status online/healthy
                if STRICT_HEALTH:
                    try:
                        j = r.json()
                        data = j.get('response') if isinstance(j, dict) else None
                        if not isinstance(data, dict):
                            data = j if isinstance(j, dict) else {}
                        ok = data.get('status') in ('online', 'healthy')
                        if ok:
                            break
                        last_err = f"status json={j}"
                    except Exception as e:
                        last_err = f'json parse error: {e}'
                else:
                    break
            last_err = f'status={r.status_code} body={r.text}'
        except Exception as e:
            last_err = str(e)
        time.sleep(1)
    else:
        pytest.fail(f'Doorman backend not healthy at {base_url}/api/status: {last_err}')

    # Login as admin
    auth = c.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert 'access_token' in auth.get('response', auth), 'login did not return access_token'
    return c


@pytest.fixture(autouse=True)
def ensure_session_and_relaxed_limits(client: LiveClient):
    """Per-test guard: ensure we're authenticated and not rate-limited.

    - Re-login if session is invalid (status not 200/204).
    - Set very generous admin rate/throttle to avoid cross-test 429s.
    """
    try:
        r = client.get('/platform/authorization/status')
        if r.status_code not in (200, 204):
            from config import ADMIN_EMAIL, ADMIN_PASSWORD
            client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    except Exception:
        from config import ADMIN_EMAIL, ADMIN_PASSWORD
        client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    # Relax rate limits to avoid interference between tests
    try:
        client.put('/platform/user/admin', json={
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


def pytest_addoption(parser):
    parser.addoption('--graph', action='store_true', default=False, help='Force GraphQL tests')
    parser.addoption('--grpc', action='store_true', default=False, help='Force gRPC tests')
