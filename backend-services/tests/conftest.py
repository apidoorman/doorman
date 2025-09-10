import os
import sys
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Set environment for in-memory operation and predictable auth
os.environ.setdefault("MEM_OR_REDIS", "MEM")
os.environ.setdefault("MEM_OR_EXTERNAL", "MEM")
os.environ.setdefault("HTTPS_ONLY", "false")
os.environ.setdefault("HTTPS_ENABLED", "false")
os.environ.setdefault("STRICT_RESPONSE_ENVELOPE", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-change")
os.environ.setdefault("STARTUP_ADMIN_EMAIL", "admin@doorman.so")
os.environ.setdefault("STARTUP_ADMIN_PASSWORD", "password1")
os.environ.setdefault("MEM_ENCRYPTION_KEY", "unit-test-key-32chars-abcdef123456!!")
os.environ.setdefault("ALLOWED_HEADERS", "*")
os.environ.setdefault("ALLOW_HEADERS", "*")
os.environ.setdefault("ALLOW_METHODS", "*")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


# Import app after env is set
from doorman import doorman  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=doorman, base_url="http://testserver") as ac:
        yield ac


async def _login(client: AsyncClient) -> None:
    resp = await client.post(
        "/platform/authorization",
        json={"email": os.environ["STARTUP_ADMIN_EMAIL"], "password": os.environ["STARTUP_ADMIN_PASSWORD"]},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    # httpx AsyncClient manages cookies automatically; ensure cookie present
    assert any(c.name == "access_token_cookie" for c in client.cookies.jar), "Auth cookie missing"


@pytest_asyncio.fixture()
async def authed_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    await _login(client)
    yield client


async def create_api(client: AsyncClient, name: str, version: str, *, servers=None, groups=None):
    payload = {
        "api_name": name,
        "api_version": version,
        "api_description": f"API {name} {version}",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": groups or ["ALL"],
        "api_servers": servers or ["http://upstream.local"],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
    }
    r = await client.post("/platform/api", json=payload)
    assert r.status_code in (200, 201), r.text


async def create_endpoint(client: AsyncClient, api_name: str, version: str, method: str, uri: str, *, servers=None):
    payload = {
        "api_name": api_name,
        "api_version": version,
        "endpoint_method": method,
        "endpoint_uri": uri,
        "endpoint_description": f"{method} {uri}",
    }
    if servers is not None:
        payload["endpoint_servers"] = servers
    r = await client.post("/platform/endpoint", json=payload)
    assert r.status_code in (200, 201), r.text


async def subscribe_self(client: AsyncClient, api_name: str, version: str):
    payload = {"username": "admin", "api_name": api_name, "api_version": version}
    r = await client.post("/platform/subscription/subscribe", json=payload)
    assert r.status_code in (200, 201), r.text
