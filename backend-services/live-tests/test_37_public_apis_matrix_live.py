import os
from typing import Any, Dict, List, Tuple

import pytest

pytestmark = [pytest.mark.public]


# -----------------------------
# Provision N public APIs (auth optional) across all types
# -----------------------------


def _mk_api(client, name: str, ver: str, servers: List[str], extra: Dict[str, Any] | None = None) -> None:
    r = client.post(
        "/platform/api",
        json={
            "api_name": name,
            "api_version": ver,
            "api_description": f"Public API {name}",
            "api_servers": servers,
            "api_type": "REST",
            "api_public": True,
            "api_allowed_roles": ["admin"],
            "api_allowed_groups": ["ALL"],
            "api_allowed_retry_count": 0,
            "active": True,
            **(extra or {}),
        },
    )
    assert r.status_code in (200, 201), r.text


def _mk_endpoint(client, name: str, ver: str, method: str, uri: str) -> None:
    r = client.post(
        "/platform/endpoint",
        json={
            "api_name": name,
            "api_version": ver,
            "endpoint_method": method,
            "endpoint_uri": uri,
            "endpoint_description": f"{method} {uri}",
        },
    )
    if r.status_code not in (200, 201):
        try:
            body = r.json()
            code = body.get("error_code") or body.get("response", {}).get("error_code")
            # Treat idempotent creation as success
            if code == "END001":
                return
        except Exception:
            pass
        assert r.status_code in (200, 201), r.text


@pytest.fixture(scope="session")
def provisioned_public_apis(client):
    """Create 20+ public APIs using real external upstreams (no mocks).

    If DOORMAN_TEST_CLEANUP is set to 1/true, tear down provisioned
    APIs/endpoints/subscriptions at the end of the session.
    """
    catalog: List[Tuple[str, str, str, Dict[str, Any]]] = []
    ver = "v1"

    def add_rest(name: str, server: str, uri: str):
        _mk_api(client, name, ver, [server])
        # Normalize endpoint registration to exclude querystring; gateway matches path-only.
        path_only = uri.split("?")[0]
        _mk_endpoint(client, name, ver, "GET", path_only)
        catalog.append(("REST", name, ver, {"uri": uri}))

    # REST (12+)
    add_rest("rest_httpbin_get", "https://httpbin.org", "/get")
    add_rest("rest_httpbin_any", "https://httpbin.org", "/anything")
    add_rest("rest_jsonplaceholder_post", "https://jsonplaceholder.typicode.com", "/posts/1")
    add_rest("rest_jsonplaceholder_user", "https://jsonplaceholder.typicode.com", "/users/1")
    add_rest("rest_dog_ceo", "https://dog.ceo/api", "/breeds/image/random")
    add_rest("rest_catfact", "https://catfact.ninja", "/fact")
    add_rest("rest_bored", "https://www.boredapi.com/api", "/activity")
    add_rest("rest_chuck", "https://api.chucknorris.io/jokes", "/random")
    add_rest("rest_exchange", "https://open.er-api.com/v6/latest", "/USD")
    add_rest("rest_ipify", "https://api.ipify.org", "/?format=json")
    add_rest("rest_genderize", "https://api.genderize.io", "/?name=peter")
    add_rest("rest_agify", "https://api.agify.io", "/?name=lucy")

    # SOAP (3)
    def add_soap(name: str, server: str, uri: str):
        _mk_api(client, name, ver, [server])
        _mk_endpoint(client, name, ver, "POST", uri)
        catalog.append(("SOAP", name, ver, {"uri": uri}))

    add_soap("soap_calc", "http://www.dneonline.com", "/calculator.asmx")
    add_soap(
        "soap_numberconv",
        "https://www.dataaccess.com",
        "/webservicesserver/NumberConversion.wso",
    )
    add_soap(
        "soap_countryinfo",
        "http://webservices.oorsprong.org",
        "/websamples.countryinfo/CountryInfoService.wso",
    )

    # GraphQL (3) - Upstreams must expose /graphql path
    def add_gql(name: str, server: str, query: str):
        _mk_api(client, name, ver, [server])
        _mk_endpoint(client, name, ver, "POST", "/graphql")
        catalog.append(("GRAPHQL", name, ver, {"query": query}))

    add_gql(
        "gql_rickandmorty",
        "https://rickandmortyapi.com",
        "{ characters(page: 1) { info { count } } }",
    )
    add_gql(
        "gql_spacex",
        "https://api.spacex.land",
        "{ company { name } }",
    )
    # Third GraphQL: some public endpoints are not at /graphql and may 404; still real and non-auth
    add_gql(
        "gql_countries",
        "https://countries.trevorblades.com",
        "{ country(code: \"US\") { name } }",
    )

    # gRPC (3) - Use public grpcbin with published Empty endpoint; upload minimal proto preserving package
    PROTO_GRPCBIN = (
        'syntax = "proto3";\n'
        'package grpcbin;\n'
        'import "google/protobuf/empty.proto";\n'
        'service GRPCBin {\n'
        '  rpc Empty (google.protobuf.Empty) returns (google.protobuf.Empty);\n'
        '}\n'
    )

    def add_grpc(name: str, server: str, method: str, message: Dict[str, Any]):
        files = {"file": ("grpcbin.proto", PROTO_GRPCBIN.encode("utf-8"), "application/octet-stream")}
        r_up = client.post(f"/platform/proto/{name}/{ver}", files=files)
        assert r_up.status_code == 200, r_up.text
        _mk_api(client, name, ver, [server], extra={"api_grpc_package": "grpcbin"})
        _mk_endpoint(client, name, ver, "POST", "/grpc")
        catalog.append(("GRPC", name, ver, {"method": method, "message": message}))

    # Cover both plaintext and TLS endpoints
    add_grpc("grpc_bin1", "grpc://grpcb.in:9000", "GRPCBin.Empty", {})
    add_grpc("grpc_bin2", "grpcs://grpcb.in:9001", "GRPCBin.Empty", {})
    add_grpc("grpc_bin3", "grpc://grpcb.in:9000", "GRPCBin.Empty", {})

    # Ensure minimum of 20 APIs
    assert len(catalog) >= 20
    try:
        yield catalog
    finally:
        if str(os.getenv('DOORMAN_TEST_CLEANUP', '')).lower() in ('1', 'true', 'yes', 'on'):
            for kind, name, ver, meta in list(catalog):
                # Best-effort cleanup
                try:
                    if kind == 'REST':
                        # Use registered path (without query) for deletion
                        method, uri = 'GET', (meta.get('uri', '/') or '/').split('?')[0]
                    elif kind == 'SOAP':
                        method, uri = 'POST', meta.get('uri', '/')
                    elif kind == 'GRAPHQL':
                        method, uri = 'POST', '/graphql'
                    elif kind == 'GRPC':
                        method, uri = 'POST', '/grpc'
                    else:
                        method, uri = 'GET', '/'
                    client.delete(f'/platform/endpoint/{method}/{name}/{ver}{uri}')
                except Exception:
                    pass
                try:
                    if kind == 'GRPC':
                        # remove uploaded proto to unwind generated artifacts server-side
                        client.delete(f'/platform/proto/{name}/{ver}')
                except Exception:
                    pass
                try:
                    client.post(
                        '/platform/subscription/unsubscribe',
                        json={'api_name': name, 'api_version': ver, 'username': 'admin'},
                    )
                except Exception:
                    pass
                try:
                    client.delete(f'/platform/api/{name}/{ver}')
                except Exception:
                    pass


def _call_public(client, kind: str, name: str, ver: str, meta: Dict[str, Any]):
    # Do not skip live checks; tolerate upstream variability instead
    if kind == "REST":
        uri = meta["uri"]
        return client.get(f"/api/rest/{name}/{ver}{uri}")
    if kind == "SOAP":
        uri = meta["uri"]
        # Minimal SOAP envelopes for public services
        if "calculator.asmx" in uri:
            envelope = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><Add xmlns=\"http://tempuri.org/\"><intA>1</intA><intB>2</intB></Add>"
                "</soap:Body></soap:Envelope>"
            )
        elif "NumberConversion" in uri:
            envelope = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><NumberToWords xmlns=\"http://www.dataaccess.com/webservicesserver/\">"
                "<ubiNum>7</ubiNum></NumberToWords></soap:Body></soap:Envelope>"
            )
        else:
            envelope = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><CapitalCity xmlns=\"http://www.oorsprong.org/websamples.countryinfo\">"
                "<sCountryISOCode>US</sCountryISOCode></CapitalCity></soap:Body></soap:Envelope>"
            )
        return client.post(
            f"/api/soap/{name}/{ver}{uri}", data=envelope, headers={"Content-Type": "text/xml"}
        )
    if kind == "GRAPHQL":
        q = meta.get("query") or "{ hello }"
        return client.post(
            f"/api/graphql/{name}", json={"query": q}, headers={"X-API-Version": ver}
        )
    if kind == "GRPC":
        body = {"method": meta["method"], "message": meta.get("message") or {}}
        return client.post(f"/api/grpc/{name}", json=body, headers={"X-API-Version": ver})
    raise AssertionError(f"Unknown kind: {kind}")


def _ok_status(code: int) -> bool:
    # Accept any non-auth failure outcome; upstreams may 400/404/500.
    return code not in (401, 403)


# -----------------------------
# 100+ parameterized live checks
# -----------------------------


@pytest.mark.parametrize("repeat", list(range(1, 2)))
@pytest.mark.parametrize("idx", list(range(0, 20)))
def test_public_api_reachability_smoke(client, provisioned_public_apis, idx, repeat):
    kind, name, ver, meta = provisioned_public_apis[idx]
    r = _call_public(client, kind, name, ver, meta)
    # Live upstreams can legitimately return 4xx/5xx; only assert it's not an auth failure.
    assert _ok_status(r.status_code), r.text


@pytest.mark.parametrize("idx", list(range(0, 20)))
def test_public_api_allows_header_forwarding(client, provisioned_public_apis, idx):
    kind, name, ver, meta = provisioned_public_apis[idx]
    # Do not skip live checks; tolerate upstream variability instead

    # Call with a custom header; Doorman may or may not forward it, only care it doesn't 401/403.
    if kind == "REST":
        r = client.get(f"/api/rest/{name}/{ver}{meta['uri']}", headers={"X-Test": "1"})
    elif kind == "SOAP":
        envelope = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
            "  <soap:Body><EchoRequest><message>hi</message></EchoRequest></soap:Body>"
            "</soap:Envelope>"
        )
        r = client.post(
            f"/api/soap/{name}/{ver}{meta['uri']}",
            data=envelope,
            headers={"Content-Type": "text/xml", "X-Test": "1"},
        )
    elif kind == "GRAPHQL":
        q = meta.get("query") or "{ hello }"
        r = client.post(
            f"/api/graphql/{name}",
            json={"query": q},
            headers={"X-API-Version": ver, "X-Test": "1"},
        )
    else:  # GRPC
        body = {"method": meta.get("method") or "Greeter.Hello", "message": {"name": "X"}}
        r = client.post(
            f"/api/grpc/{name}", json=body, headers={"X-API-Version": ver, "X-Test": "1"}
        )
    # Live upstreams can legitimately return non-200; only require non-auth failure.
    assert _ok_status(r.status_code), r.text


@pytest.mark.parametrize("idx", list(range(0, 20)))
def test_public_api_cors_preflight(client, provisioned_public_apis, idx):
    kind, name, ver, meta = provisioned_public_apis[idx]
    if meta.get("skip"):
        pytest.skip(f"Upstream for {kind} not available in this environment")

    origin = "https://example.test"
    if kind == "REST":
        r = client.options(
            f"/api/rest/{name}/{ver}{meta['uri']}",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Test",
            },
        )
    elif kind == "SOAP":
        r = client.options(
            f"/api/soap/{name}/{ver}{meta['uri']}",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
    elif kind == "GRAPHQL":
        r = client.options(
            f"/api/graphql/{name}",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
                "X-API-Version": ver,
            },
        )
    else:  # GRPC
        r = client.options(
            f"/api/grpc/{name}",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
                "X-API-Version": ver,
            },
        )
    # Preflight should be 200/204 for REST/SOAP/GRAPHQL under sane CORS settings.
    if kind in ("REST", "SOAP", "GRAPHQL", "GRPC"):
        assert r.status_code in (200, 204), r.text
    else:
        assert _ok_status(r.status_code), r.text


@pytest.mark.parametrize("idx", list(range(0, 20)))
def test_public_api_querystring_passthrough(client, provisioned_public_apis, idx):
    kind, name, ver, meta = provisioned_public_apis[idx]
    if meta.get("skip"):
        pytest.skip(f"Upstream for {kind} not available in this environment")

    if kind == "REST":
        r = client.get(f"/api/rest/{name}/{ver}{meta['uri']}?a=1&b=two")
    elif kind == "SOAP":
        envelope = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<soap:Envelope xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
            "  <soap:Body><EchoRequest><message>qs</message></EchoRequest></soap:Body>"
            "</soap:Envelope>"
        )
        r = client.post(
            f"/api/soap/{name}/{ver}{meta['uri']}?x=y",
            data=envelope,
            headers={"Content-Type": "text/xml"},
        )
    elif kind == "GRAPHQL":
        q = meta.get("query") or "{ hello }"
        r = client.post(
            f"/api/graphql/{name}?trace=true",
            json={"query": q},
            headers={"X-API-Version": ver},
        )
    else:  # GRPC
        body = {"method": meta.get("method") or "Greeter.Hello", "message": {"name": "Q"}}
        r = client.post(
            f"/api/grpc/{name}?trace=true", json=body, headers={"X-API-Version": ver}
        )
    # Accept non-200 outcomes as long as not auth failure.
    assert _ok_status(r.status_code), r.text


@pytest.mark.parametrize("idx", list(range(0, 20)))
def test_public_api_multiple_calls_stability(client, provisioned_public_apis, idx):
    kind, name, ver, meta = provisioned_public_apis[idx]
    # Two quick back-to-back calls to catch simple race/limits; only assert not auth failure.
    r1 = _call_public(client, kind, name, ver, meta)
    r2 = _call_public(client, kind, name, ver, meta)
    # Both calls should avoid auth failures; allow non-200 codes.
    assert _ok_status(r1.status_code), r1.text
    assert _ok_status(r2.status_code), r2.text


@pytest.mark.parametrize("idx", list(range(0, 20)))
def test_public_api_subscribe_and_call(client, provisioned_public_apis, idx):
    kind, name, ver, meta = provisioned_public_apis[idx]
    # Subscribe admin to the API; treat already-subscribed as success
    s = client.post(
        '/platform/subscription/subscribe',
        json={'api_name': name, 'api_version': ver, 'username': 'admin'},
    )
    if s.status_code not in (200, 201):
        try:
            b = s.json()
            code = b.get('error_code') or b.get('response', {}).get('error_code')
            assert code == 'SUB004', s.text  # already subscribed
        except Exception:
            raise

    # Now call through the gateway; should not auth-fail
    r = _call_public(client, kind, name, ver, meta)
    # After subscription, ensure no auth failure; accept non-200 from upstreams.
    assert _ok_status(r.status_code), r.text
