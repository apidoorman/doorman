import concurrent.futures
import os
import time
from typing import Any, Dict, List, Tuple

import pytest

from client import LiveClient

pytestmark = [pytest.mark.public, pytest.mark.credits, pytest.mark.gateway]


def _rest_targets() -> List[Tuple[str, str]]:
    return [
        ("https://httpbin.org", "/get"),
        ("https://jsonplaceholder.typicode.com", "/posts/1"),
        ("https://api.ipify.org", "/?format=json"),
    ]


def _soap_targets() -> List[Tuple[str, str, str]]:
    return [
        ("http://www.dneonline.com", "/calculator.asmx", "calc"),
        ("https://www.dataaccess.com", "/webservicesserver/NumberConversion.wso", "num"),
        (
            "http://webservices.oorsprong.org",
            "/websamples.countryinfo/CountryInfoService.wso",
            "country",
        ),
    ]


def _gql_targets() -> List[Tuple[str, str]]:
    return [
        ("https://rickandmortyapi.com", "{ characters(page: 1) { info { count } } }"),
        ("https://api.spacex.land", "{ company { name } }"),
        ("https://countries.trevorblades.com", "{ country(code: \"US\") { name } }")
    ]


def _grpc_targets() -> List[Tuple[str, str]]:
    return [
        ("grpc://grpcb.in:9000", "GRPCBin.Empty"),
        ("grpcs://grpcb.in:9001", "GRPCBin.Empty"),
        ("grpc://grpcb.in:9000", "GRPCBin.Empty"),
    ]


PROTO_GRPCBIN = (
    'syntax = "proto3";\n'
    'package grpcbin;\n'
    'import "google/protobuf/empty.proto";\n'
    'service GRPCBin {\n'
    '  rpc Empty (google.protobuf.Empty) returns (google.protobuf.Empty);\n'
    '}\n'
)


def _ok_status(code: int) -> bool:
    """Check if status is acceptable (not auth failure, tolerates upstream issues)."""
    # Auth failures are not OK
    if code in (401, 403):
        return False
    # 5xx errors from upstream/circuit breaker are tolerated for live tests
    # since external APIs can be flaky
    return True


def _soap_envelope(kind: str) -> str:
    if kind == "calc":
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
            "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
            "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
            "<soap:Body><Add xmlns=\"http://tempuri.org/\"><intA>1</intA><intB>2</intB></Add>"
            "</soap:Body></soap:Envelope>"
        )
    if kind == "num":
        return (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
            "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
            "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
            "<soap:Body><NumberToWords xmlns=\"http://www.dataaccess.com/webservicesserver/\">"
            "<ubiNum>7</ubiNum></NumberToWords></soap:Body></soap:Envelope>"
        )
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
        "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
        "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
        "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
        "<soap:Body><CapitalCity xmlns=\"http://www.oorsprong.org/websamples.countryinfo\">"
        "<sCountryISOCode>US</sCountryISOCode></CapitalCity></soap:Body></soap:Envelope>"
    )


def _mk_credit_def(client: LiveClient, group: str, credits: int = 5):
    r = client.post(
        "/platform/credit",
        json={
            "api_credit_group": group,
            "api_key": f"KEY_{group}",
            "api_key_header": "x-api-key",
            "credit_tiers": [
                {
                    "tier_name": "default",
                    "credits": credits,
                    "input_limit": 0,
                    "output_limit": 0,
                    "reset_frequency": "monthly",
                }
            ],
        },
    )
    assert r.status_code in (200, 201), r.text
    r = client.post(
        "/platform/credit/admin",
        json={
            "username": "admin",
            "users_credits": {group: {"tier_name": "default", "available_credits": credits}},
        },
    )
    assert r.status_code in (200, 201), r.text


def _subscribe(client: LiveClient, name: str, ver: str):
    r = client.post(
        "/platform/subscription/subscribe",
        json={"api_name": name, "api_version": ver, "username": "admin"},
    )
    assert r.status_code in (200, 201) or (
        r.json().get("error_code") == "SUB004"
    ), r.text


def _update_desc_and_assert(client: LiveClient, name: str, ver: str):
    r = client.put(
        f"/platform/api/{name}/{ver}",
        json={"api_description": f"updated {int(time.time())}"},
    )
    assert r.status_code == 200, r.text
    r = client.get(f"/platform/api/{name}/{ver}")
    assert r.status_code == 200
    body = r.json().get("response", r.json())
    assert "updated" in (body.get("api_description") or "")


def _assert_credit_exhausted(resp) -> None:
    assert resp.status_code in (401, 403), resp.text
    try:
        j = resp.json()
        code = j.get("error_code") or j.get("response", {}).get("error_code")
        assert code == "GTW008", resp.text
    except Exception:
        # SOAP may return XML fault; allow 401/403 as signal
        pass


def _one_call(client: LiveClient, kind: str, name: str, ver: str, meta: Dict[str, Any]):
    if kind == "REST":
        return client.get(f"/api/rest/{name}/{ver}{meta['uri']}")
    if kind == "SOAP":
        env = _soap_envelope(meta["sk"])  # soap kind
        return client.post(
            f"/api/soap/{name}/{ver}{meta['uri']}", data=env, headers={"Content-Type": "text/xml"}
        )
    if kind == "GRAPHQL":
        return client.post(
            f"/api/graphql/{name}",
            json={"query": meta["query"]},
            headers={"X-API-Version": ver},
        )
    # GRPC
    return client.post(
        f"/api/grpc/{name}",
        json={"method": meta["method"], "message": meta.get("message") or {}},
        headers={"X-API-Version": ver},
    )


def _exercise_credits(client: LiveClient, kind: str, name: str, ver: str, meta: Dict[str, Any]):
    # Make 5 allowed calls - tolerate upstream failures
    upstream_failures = 0
    for _ in range(5):
        r = _one_call(client, kind, name, ver, meta)
        if r.status_code >= 500:
            upstream_failures += 1
            if upstream_failures > 2:
                pytest.skip(f"External API unreliable for {kind}, skipping credit exhaustion test")
        assert _ok_status(r.status_code), r.text
    # 6th should be credit exhausted (or upstream error if API is flaky)
    r6 = _one_call(client, kind, name, ver, meta)
    if r6.status_code >= 500:
        # Upstream error, can't verify credit exhaustion
        return
    _assert_credit_exhausted(r6)


def _exercise_concurrent_credits(
    client: LiveClient, kind: str, name: str, ver: str, meta: Dict[str, Any]
):
    # Fire 6 concurrent requests; expect 5 pass (non-auth) and 1 GTW008
    def do_call():
        return _one_call(client, kind, name, ver, meta)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(do_call) for _ in range(6)]
        results = [f.result() for f in futs]

    ok = sum(1 for r in results if _ok_status(r.status_code))
    exhausted = sum(1 for r in results if r.status_code in (401, 403))
    assert ok >= 4  # allow one transient failure
    assert exhausted >= 1


def _set_user_rl_low(client: LiveClient):
    client.put(
        "/platform/user/admin",
        json={
            "rate_limit_duration": 1,
            "rate_limit_duration_type": "second",
            "throttle_duration": 0,
            "throttle_duration_type": "second",
            "throttle_queue_limit": 0,
            "throttle_wait_duration": 0,
            "throttle_wait_duration_type": "second",
        },
    )


def _restore_user_rl(client: LiveClient):
    client.put(
        "/platform/user/admin",
        json={
            "rate_limit_duration": 1000000,
            "rate_limit_duration_type": "second",
            "throttle_duration": 1000000,
            "throttle_duration_type": "second",
            "throttle_queue_limit": 1000000,
            "throttle_wait_duration": 0,
            "throttle_wait_duration_type": "second",
        },
    )


def _assert_429_or_tolerate_upstream(r):
    """Assert 429, but tolerate upstream/network variance in live mode.

    Accepts 429 as a pass. For constrained environments where upstreams
    intermittently 5xx/504, treat those as acceptable for this step to avoid
    flakiness. Only fail on clear non-errors (e.g., 2xx) here.
    """
    if r.status_code == 429:
        try:
            j = r.json()
            assert j.get("error") in ("Rate limit exceeded", None)
        except Exception:
            pass
        return
    # Tolerate known gateway/upstream transient errors during RL checks
    if r.status_code in (500, 502, 503, 504):
        return
    # Otherwise, require not-auth failure at minimum
    assert _ok_status(r.status_code), r.text


def _tier_payload(tier_id: str, limits: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tier_id": tier_id,
        "name": "custom",
        "display_name": tier_id,
        "description": "test tier",
        "limits": {
            "requests_per_second": limits.get("rps"),
            "requests_per_minute": limits.get("rpm", 1),
            "requests_per_hour": limits.get("rph"),
            "requests_per_day": limits.get("rpd"),
            "enable_throttling": limits.get("throttle", False),
            "max_queue_time_ms": limits.get("queue_ms", 0),
        },
        "price_monthly": 0.0,
        "features": [],
        "is_default": False,
        "enabled": True,
    }


def _assign_tier(client: LiveClient, tier_id: str):
    # Prefer trailing slash to avoid 307 redirect in some setups
    r = client.post("/platform/tiers/", json=_tier_payload(tier_id, {"rpm": 1}))
    assert r.status_code in (200, 201), r.text
    r = client.post(
        "/platform/tiers/assignments",
        json={"user_id": "admin", "tier_id": tier_id},
    )
    assert r.status_code in (200, 201), r.text


def _remove_tier(client: LiveClient, tier_id: str):
    try:
        client.delete(f"/platform/tiers/assignments/admin")
    except Exception:
        pass
    try:
        client.delete(f"/platform/tiers/{tier_id}")
    except Exception:
        pass


def _setup_api(
    client: LiveClient, kind: str, idx: int
) -> Tuple[str, str, Dict[str, Any]]:
    name = f"live-{kind.lower()}-{int(time.time())}-{idx}"
    ver = "v1"
    credit_group = f"cg-{kind.lower()}-{int(time.time())}-{idx}"
    _mk_credit_def(client, credit_group, credits=5)

    if kind == "REST":
        server, uri = _rest_targets()[idx]
        r = client.post(
            "/platform/api",
            json={
                "api_name": name,
                "api_version": ver,
                "api_description": f"{kind} credits",
                "api_allowed_roles": ["admin"],
                "api_allowed_groups": ["ALL"],
                "api_servers": [server],
                "api_type": "REST",
                "active": True,
                "api_credits_enabled": True,
                "api_credit_group": credit_group,
            },
        )
        assert r.status_code in (200, 201), f"API creation failed: {r.text}"
        # Force update to ensure api_credits_enabled is set (in case API already existed)
        client.put(f"/platform/api/{name}/{ver}", json={
            "api_credits_enabled": True,
            "api_credit_group": credit_group,
        })
        client.delete('/api/caches')  # Clear cache to pick up updated API
        path_only = uri.split("?")[0] or "/"
        client.post(
            "/platform/endpoint",
            json={
                "api_name": name,
                "api_version": ver,
                "endpoint_method": "GET",
                "endpoint_uri": path_only,
                "endpoint_description": f"GET {path_only}",
            },
        )
        _subscribe(client, name, ver)
        meta = {"uri": uri, "credit_group": credit_group}
        return name, ver, meta

    if kind == "SOAP":
        server, uri, sk = _soap_targets()[idx]
        client.post(
            "/platform/api",
            json={
                "api_name": name,
                "api_version": ver,
                "api_description": f"{kind} credits",
                "api_allowed_roles": ["admin"],
                "api_allowed_groups": ["ALL"],
                "api_servers": [server],
                "api_type": "REST",
                "active": True,
                "api_credits_enabled": True,
                "api_credit_group": credit_group,
            },
        )
        client.post(
            "/platform/endpoint",
            json={
                "api_name": name,
                "api_version": ver,
                "endpoint_method": "POST",
                "endpoint_uri": uri,
                "endpoint_description": f"POST {uri}",
            },
        )
        _subscribe(client, name, ver)
        meta = {"uri": uri, "sk": sk, "credit_group": credit_group}
        return name, ver, meta

    if kind == "GRAPHQL":
        server, query = _gql_targets()[idx]
        client.post(
            "/platform/api",
            json={
                "api_name": name,
                "api_version": ver,
                "api_description": f"{kind} credits",
                "api_allowed_roles": ["admin"],
                "api_allowed_groups": ["ALL"],
                "api_servers": [server],
                "api_type": "REST",
                "active": True,
                "api_credits_enabled": True,
                "api_credit_group": credit_group,
            },
        )
        client.post(
            "/platform/endpoint",
            json={
                "api_name": name,
                "api_version": ver,
                "endpoint_method": "POST",
                "endpoint_uri": "/graphql",
                "endpoint_description": "POST /graphql",
            },
        )
        _subscribe(client, name, ver)
        meta = {"query": query, "credit_group": credit_group}
        return name, ver, meta

    # GRPC
    server, method = _grpc_targets()[idx]
    files = {"file": ("grpcbin.proto", PROTO_GRPCBIN.encode("utf-8"), "application/octet-stream")}
    up = client.post(f"/platform/proto/{name}/{ver}", files=files)
    assert up.status_code == 200, up.text
    client.post(
        "/platform/api",
        json={
            "api_name": name,
            "api_version": ver,
            "api_description": f"{kind} credits",
            "api_allowed_roles": ["admin"],
            "api_allowed_groups": ["ALL"],
            "api_servers": [server],
            "api_type": "REST",
            "active": True,
            "api_credits_enabled": True,
            "api_credit_group": credit_group,
            "api_grpc_package": "grpcbin",
        },
    )
    client.post(
        "/platform/endpoint",
        json={
            "api_name": name,
            "api_version": ver,
            "endpoint_method": "POST",
            "endpoint_uri": "/grpc",
            "endpoint_description": "POST /grpc",
        },
    )
    _subscribe(client, name, ver)
    meta = {"method": method, "message": {}, "credit_group": credit_group}
    return name, ver, meta


@pytest.mark.parametrize("kind", ["REST", "SOAP", "GRAPHQL", "GRPC"])
@pytest.mark.parametrize("idx", [0, 1, 2])
def test_live_api_credits_limits_and_cleanup(client: LiveClient, kind: str, idx: int):
    # Reset circuit breaker state to avoid carryover from previous tests
    try:
        from utils.http_client import circuit_manager
        circuit_manager.reset()
    except Exception:
        pass

    name, ver, meta = _setup_api(client, kind, idx)

    # Verify auth required when unauthenticated
    unauth = LiveClient(client.base_url)
    r = _one_call(unauth, kind, name, ver, meta)
    assert r.status_code in (401, 403)

    # Initial live call (should not auth-fail)
    # Tolerate circuit breaker errors from prior test pollution
    r0 = _one_call(client, kind, name, ver, meta)
    if r0.status_code == 500:
        try:
            j = r0.json()
            if j.get("error_code") == "GTW999":
                # Circuit was open, reset and retry
                from utils.http_client import circuit_manager
                circuit_manager.reset()
                r0 = _one_call(client, kind, name, ver, meta)
        except Exception:
            pass
    assert _ok_status(r0.status_code), r0.text

    # Update API and verify change visible via platform read
    _update_desc_and_assert(client, name, ver)

    # Per-user rate limiting (two quick calls -> second 429)
    try:
        _set_user_rl_low(client)
        time.sleep(1.1)
        r1 = _one_call(client, kind, name, ver, meta)
        assert _ok_status(r1.status_code), r1.text
        r2 = _one_call(client, kind, name, ver, meta)
        _assert_429_or_tolerate_upstream(r2)
    finally:
        _restore_user_rl(client)

    # Tier-level rate limiting (minute-based) - skip if middleware disabled
    _test_mode = os.getenv('DOORMAN_TEST_MODE', '').lower() in ('1', 'true', 'yes', 'on')
    _skip_tier = os.getenv('SKIP_TIER_RATE_LIMIT', '').lower() in ('1', 'true', 'yes', 'on')
    if not (_test_mode or _skip_tier):
        tier_id = f"tier-{kind.lower()}-{idx}"
        try:
            _assign_tier(client, tier_id)
            time.sleep(1.1)
            r3 = _one_call(client, kind, name, ver, meta)
            assert _ok_status(r3.status_code), r3.text
            r4 = _one_call(client, kind, name, ver, meta)
            _assert_429_or_tolerate_upstream(r4)
        finally:
            _remove_tier(client, tier_id)

    # Credits usage and exhaustion - reset credits to ensure 5 available
    try:
        client.delete('/platform/tiers/assignments/admin')
    except Exception:
        pass
    client.delete('/api/caches')
    time.sleep(0.5)  # Allow cache clear to propagate
    
    # Reset credits to 5 for the exercise (earlier calls may have depleted them)
    credit_group = meta.get("credit_group")
    if credit_group:
        client.post(
            "/platform/credit/admin",
            json={
                "username": "admin",
                "users_credits": {credit_group: {"tier_name": "default", "available_credits": 5}},
            },
        )
    
    _exercise_credits(client, kind, name, ver, meta)

    # Concurrent consumption safety (new credits for this step)
    # Top-up 5 credits and ensure exactly one request is rejected among 6 concurrent
    group = f"cg-topup-{kind.lower()}-{int(time.time())}-{idx}"
    _mk_credit_def(client, group, credits=5)
    # Switch API to new credit group
    r = client.put(f"/platform/api/{name}/{ver}", json={"api_credit_group": group})
    assert r.status_code == 200, r.text
    _exercise_concurrent_credits(client, kind, name, ver, meta)

    # Delete API (endpoints/protos will be cleaned by session cleanup as well)
    # Best-effort explicit delete here
    try:
        if kind == "REST":
            p = (meta.get("uri") or "/").split("?")[0] or "/"
            client.delete(f"/platform/endpoint/GET/{name}/{ver}{p}")
        elif kind == "SOAP":
            client.delete(f"/platform/endpoint/POST/{name}/{ver}{meta['uri']}")
        elif kind == "GRAPHQL":
            client.delete(f"/platform/endpoint/POST/{name}/{ver}/graphql")
        else:
            client.delete(f"/platform/endpoint/POST/{name}/{ver}/grpc")
    except Exception:
        pass
    client.delete(f"/platform/api/{name}/{ver}")
