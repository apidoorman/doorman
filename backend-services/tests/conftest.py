"""
Pytest configuration for backend-services tests.

Ensures the backend-services directory is on sys.path so imports like
`from utils...` resolve correctly when tests run from the repo root in CI.
"""

import os
import sys

# Ensure critical env before app modules import
os.environ.setdefault("MEM_OR_EXTERNAL", "MEM")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("STARTUP_ADMIN_EMAIL", "admin@doorman.so")
os.environ.setdefault("STARTUP_ADMIN_PASSWORD", "password1")

_HERE = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest_asyncio
from httpx import AsyncClient
import pytest
import asyncio


@pytest_asyncio.fixture
async def authed_client():
    # Create an authenticated httpx AsyncClient against the FastAPI app
    from doorman import doorman
    client = AsyncClient(app=doorman, base_url="http://testserver")
    # Login as seeded admin
    r = await client.post(
        "/platform/authorization",
        json={"email": os.environ.get("STARTUP_ADMIN_EMAIL"), "password": os.environ.get("STARTUP_ADMIN_PASSWORD")},
    )
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def client():
    from doorman import doorman
    return AsyncClient(app=doorman, base_url="http://testserver")


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test helpers expected by some suites
async def create_api(client: AsyncClient, api_name: str, api_version: str):
    payload = {
        "api_name": api_name,
        "api_version": api_version,
        "api_description": f"{api_name} {api_version}",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": ["http://upstream.test"],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
    }
    r = await client.post("/platform/api", json=payload)
    assert r.status_code in (200, 201), r.text
    return r


async def create_endpoint(client: AsyncClient, api_name: str, api_version: str, method: str, uri: str):
    payload = {
        "api_name": api_name,
        "api_version": api_version,
        "endpoint_method": method,
        "endpoint_uri": uri,
        "endpoint_description": f"{method} {uri}",
    }
    r = await client.post("/platform/endpoint", json=payload)
    assert r.status_code in (200, 201), r.text
    return r


async def subscribe_self(client: AsyncClient, api_name: str, api_version: str):
    # Subscribe the logged-in user (admin)
    r_me = await client.get("/platform/user/me")
    username = (r_me.json().get("username") if r_me.status_code == 200 else "admin")
    r = await client.post(
        "/platform/subscription/subscribe",
        json={"username": username, "api_name": api_name, "api_version": api_version},
    )
    assert r.status_code in (200, 201), r.text
    return r
