import os
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from parity.python.contract_capture import (  # noqa: E402
    RecordingAsyncClient,
    assert_fixture_matches,
    fixture_path,
    load_fixture,
    response_contract,
    scenario_fixture,
    write_fixture,
)

FIXTURES_DIR = REPO_ROOT / "parity" / "contracts" / "fixtures"
UPDATE_FIXTURES = os.getenv("UPDATE_PARITY_CONTRACTS", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


async def _create_api(
    client,
    name: str,
    version: str = "v1",
    *,
    servers: list[str] | None = None,
    public: bool = False,
    allowed_headers: list[str] | None = None,
) -> None:
    payload = {
        "api_name": name,
        "api_version": version,
        "api_description": f"{name} {version}",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": servers or ["http://upstream.test"],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
        "api_public": public,
    }
    if allowed_headers is not None:
        payload["api_allowed_headers"] = allowed_headers
    response = await client.post("/platform/api", json=payload)
    assert response.status_code in (200, 201), response.text


async def _create_endpoint(
    client,
    name: str,
    version: str,
    method: str,
    uri: str,
    *,
    servers: list[str] | None = None,
) -> None:
    payload = {
        "api_name": name,
        "api_version": version,
        "endpoint_method": method,
        "endpoint_uri": uri,
        "endpoint_description": f"{method} {uri}",
    }
    if servers is not None:
        payload["endpoint_servers"] = servers
    response = await client.post("/platform/endpoint", json=payload)
    assert response.status_code in (200, 201), response.text


async def _subscribe_admin(client, name: str, version: str = "v1") -> None:
    response = await client.post(
        "/platform/subscription/subscribe",
        json={"username": "admin", "api_name": name, "api_version": version},
    )
    assert response.status_code in (200, 201), response.text


async def _install_recording_client(monkeypatch) -> None:
    import services.gateway_service as gs

    RecordingAsyncClient.reset()
    await gs.GatewayService.aclose_http_client()
    monkeypatch.setattr(gs.httpx, "AsyncClient", RecordingAsyncClient)


def _request(method: str, path: str, *, headers: dict[str, str] | None = None, body: Any = None) -> dict[str, Any]:
    return {
        "method": method,
        "path": path,
        "query": {},
        "headers": headers or {},
        "body": body,
    }


async def capture_health_public(*, client, **_: Any) -> dict[str, Any]:
    response = await client.get("/api/health")
    return scenario_fixture(
        name="health_public",
        description="Public health probe returns the Python gateway online status.",
        tags=["read-only", "public", "health"],
        request=_request("GET", "/api/health"),
        setup={"auth": "none", "state": "default memory test app"},
        response=await response_contract(response),
        decisions={"route": "gateway.health", "auth": "not_required", "upstream": "none"},
        state_changes={},
    )


async def capture_status_unauthorized(*, client, **_: Any) -> dict[str, Any]:
    response = await client.get("/api/status")
    return scenario_fixture(
        name="status_unauthorized",
        description="Gateway status endpoint rejects unauthenticated callers.",
        tags=["read-only", "auth", "error"],
        request=_request("GET", "/api/status"),
        setup={"auth": "none", "state": "default memory test app"},
        response=await response_contract(response),
        decisions={"route": "gateway.status", "auth": "missing", "upstream": "none"},
        state_changes={},
    )


async def capture_rest_happy_path(*, authed_client, monkeypatch, **_: Any) -> dict[str, Any]:
    await _install_recording_client(monkeypatch)
    name, version = "parityhappy", "v1"
    await _create_api(authed_client, name, version)
    await _create_endpoint(authed_client, name, version, "GET", "/hello", servers=["http://upstream.test"])
    await _subscribe_admin(authed_client, name, version)

    path = f"/api/rest/{name}/{version}/hello"
    response = await authed_client.get(path)
    return scenario_fixture(
        name="rest_happy_path",
        description="Subscribed admin calls a REST endpoint and receives the upstream JSON response.",
        tags=["rest", "auth", "upstream"],
        request=_request("GET", path),
        setup={
            "api": {"name": name, "version": version, "servers": ["http://upstream.test"]},
            "endpoint": {"method": "GET", "uri": "/hello", "servers": ["http://upstream.test"]},
            "subscription": {"username": "admin"},
        },
        response=await response_contract(response),
        upstream_requests=RecordingAsyncClient.records,
        decisions={
            "protocol": "rest",
            "auth": "authenticated",
            "route_source": "endpoint",
            "selected_upstream": RecordingAsyncClient.records[0]["url"] if RecordingAsyncClient.records else None,
            "retry_count": 0,
        },
        state_changes={},
    )


async def capture_rest_request_id(*, authed_client, monkeypatch, **_: Any) -> dict[str, Any]:
    await _install_recording_client(monkeypatch)
    name, version = "parityrid", "v1"
    await _create_api(
        authed_client,
        name,
        version,
        allowed_headers=["X-Upstream-Request-ID"],
    )
    await _create_endpoint(authed_client, name, version, "GET", "/echo", servers=["http://upstream.test"])
    await _subscribe_admin(authed_client, name, version)

    path = f"/api/rest/{name}/{version}/echo"
    headers = {"X-Request-ID": "client-contract-request"}
    response = await authed_client.get(path, headers=headers)
    return scenario_fixture(
        name="rest_request_id",
        description="Request IDs are preserved in the client response and forwarded upstream.",
        tags=["rest", "headers", "upstream"],
        request=_request("GET", path, headers=headers),
        setup={
            "api": {"name": name, "version": version, "allowed_headers": ["X-Upstream-Request-ID"]},
            "endpoint": {"method": "GET", "uri": "/echo", "servers": ["http://upstream.test"]},
            "subscription": {"username": "admin"},
        },
        response=await response_contract(response),
        upstream_requests=RecordingAsyncClient.records,
        decisions={
            "protocol": "rest",
            "auth": "authenticated",
            "request_id": "preserved",
            "retry_count": 0,
        },
        state_changes={},
    )


async def capture_rest_route_precedence(*, authed_client, monkeypatch, **_: Any) -> dict[str, Any]:
    await _install_recording_client(monkeypatch)
    name, version = "parityroute", "v1"
    await _create_api(authed_client, name, version)
    await _create_endpoint(authed_client, name, version, "GET", "/ping", servers=["http://ep-a", "http://ep-b"])
    await _subscribe_admin(authed_client, name, version)
    routing = await authed_client.post(
        "/platform/routing",
        json={
            "routing_name": "contract-route",
            "routing_servers": ["http://route-a", "http://route-b"],
            "routing_description": "contract routing",
            "client_key": "contract-client",
        },
    )
    assert routing.status_code in (200, 201), routing.text

    path = f"/api/rest/{name}/{version}/ping"
    response = await authed_client.get(path, headers={"client-key": "contract-client"})
    selected = RecordingAsyncClient.records[0]["url"] if RecordingAsyncClient.records else None
    return scenario_fixture(
        name="rest_route_precedence",
        description="Client-key routing takes precedence over endpoint servers.",
        tags=["rest", "routing", "upstream"],
        request=_request("GET", path, headers={"client-key": "contract-client"}),
        setup={
            "api": {"name": name, "version": version},
            "endpoint": {"method": "GET", "uri": "/ping", "servers": ["http://ep-a", "http://ep-b"]},
            "routing": {"client_key": "contract-client", "servers": ["http://route-a", "http://route-b"]},
            "subscription": {"username": "admin"},
        },
        response=await response_contract(response),
        upstream_requests=RecordingAsyncClient.records,
        decisions={"route_source": "client_key", "selected_upstream": selected, "retry_count": 0},
        state_changes={"selected_urls": [record["url"] for record in RecordingAsyncClient.records]},
    )


async def capture_rest_round_robin_state(*, authed_client, monkeypatch, **_: Any) -> dict[str, Any]:
    await _install_recording_client(monkeypatch)
    name, version = "parityrr", "v1"
    await _create_api(authed_client, name, version)
    await _create_endpoint(authed_client, name, version, "GET", "/rr", servers=["http://rr-a", "http://rr-b"])
    await _subscribe_admin(authed_client, name, version)

    path = f"/api/rest/{name}/{version}/rr"
    first = await authed_client.get(path)
    second = await authed_client.get(path)
    return scenario_fixture(
        name="rest_round_robin_state",
        description="Repeated REST calls advance endpoint upstream selection deterministically.",
        tags=["rest", "routing", "state"],
        request={**_request("GET", path), "repeat": 2},
        setup={
            "api": {"name": name, "version": version},
            "endpoint": {"method": "GET", "uri": "/rr", "servers": ["http://rr-a", "http://rr-b"]},
            "subscription": {"username": "admin"},
        },
        response=await response_contract(second),
        upstream_requests=RecordingAsyncClient.records,
        decisions={"route_source": "endpoint", "retry_count": 0},
        state_changes={
            "selected_urls": [record["url"] for record in RecordingAsyncClient.records],
            "response_statuses": [first.status_code, second.status_code],
        },
    )


async def capture_rest_not_found(*, authed_client, monkeypatch, **_: Any) -> dict[str, Any]:
    await _install_recording_client(monkeypatch)
    name, version = "paritymissing", "v1"
    await _create_api(authed_client, name, version)
    await _create_endpoint(authed_client, name, version, "GET", "/exists", servers=["http://upstream.test"])
    await _subscribe_admin(authed_client, name, version)

    path = f"/api/rest/{name}/{version}/missing"
    response = await authed_client.get(path)
    return scenario_fixture(
        name="rest_not_found",
        description="Configured API with no matching endpoint returns the Python missing-endpoint error.",
        tags=["rest", "routing", "error"],
        request=_request("GET", path),
        setup={
            "api": {"name": name, "version": version},
            "endpoint": {"method": "GET", "uri": "/exists", "servers": ["http://upstream.test"]},
            "subscription": {"username": "admin"},
        },
        response=await response_contract(response),
        upstream_requests=RecordingAsyncClient.records,
        decisions={"route_source": "none", "error_code": "GTW003", "upstream": "not_called"},
        state_changes={},
    )


async def capture_gateway_caches_preflight(*, client, **_: Any) -> dict[str, Any]:
    response = await client.options(
        "/api/caches",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    return scenario_fixture(
        name="gateway_caches_preflight",
        description="Cache-clear preflight is accepted without authentication.",
        tags=["operations", "cors", "preflight"],
        request=_request(
            "OPTIONS",
            "/api/caches",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "DELETE",
            },
        ),
        setup={"auth": "none", "state": "default memory test app"},
        response=await response_contract(response),
        decisions={"route": "gateway.caches.options", "auth": "not_required", "upstream": "none"},
        state_changes={},
    )


SCENARIOS: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {
    "gateway_caches_preflight": capture_gateway_caches_preflight,
    "health_public": capture_health_public,
    "rest_happy_path": capture_rest_happy_path,
    "rest_not_found": capture_rest_not_found,
    "rest_request_id": capture_rest_request_id,
    "rest_round_robin_state": capture_rest_round_robin_state,
    "rest_route_precedence": capture_rest_route_precedence,
    "status_unauthorized": capture_status_unauthorized,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
async def test_python_gateway_contract_fixture(scenario_name, authed_client, client, monkeypatch):
    fixture = await SCENARIOS[scenario_name](
        authed_client=authed_client,
        client=client,
        monkeypatch=monkeypatch,
    )
    path = fixture_path(FIXTURES_DIR, scenario_name)
    if UPDATE_FIXTURES:
        write_fixture(path, fixture)
    else:
        assert_fixture_matches(path, fixture)


def test_checked_in_contract_fixtures_are_schema_valid():
    fixture_paths = sorted(FIXTURES_DIR.glob("*.json"))
    assert fixture_paths, "expected checked-in parity contract fixtures"
    names = {path.stem for path in fixture_paths}
    assert set(SCENARIOS) <= names
    for path in fixture_paths:
        fixture = load_fixture(path)
        assert fixture["name"] == path.stem
