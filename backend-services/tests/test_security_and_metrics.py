import os
import json
import time
import pytest


@pytest.mark.asyncio
async def test_security_headers_and_hsts(monkeypatch, client):
    # HSTS disabled by default
    r = await client.get("/platform/monitor/liveness")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert "Strict-Transport-Security" not in r.headers

    # Enable HTTPS_ONLY to trigger HSTS
    monkeypatch.setenv("HTTPS_ONLY", "true")
    r = await client.get("/platform/monitor/liveness")
    assert r.status_code == 200
    assert "Strict-Transport-Security" in r.headers


@pytest.mark.asyncio
async def test_body_size_limit_returns_413(monkeypatch, client):
    # Patch runtime constant used by middleware
    import doorman as appmod
    monkeypatch.setattr(appmod, "MAX_BODY_SIZE", 10, raising=False)
    payload = "x" * 100
    r = await client.post("/platform/authorization", content=payload, headers={"Content-Type": "text/plain"})
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_strict_response_envelope(monkeypatch, authed_client):
    monkeypatch.setenv("STRICT_RESPONSE_ENVELOPE", "true")
    # Use an endpoint that returns ResponseModel envelope
    r = await authed_client.get("/platform/user/admin")
    assert r.status_code == 200
    # Envelope with status_code should be present
    data = r.json()
    assert isinstance(data, dict)
    assert "status_code" in data and data["status_code"] == 200


@pytest.mark.asyncio
async def test_metrics_recording_snapshot(authed_client):
    # Create an API + endpoint and subscribe to generate an /api/* request
    from conftest import create_api, create_endpoint, subscribe_self  # type: ignore
    name, ver = "metapi", "v1"
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, "GET", "/status")
    await subscribe_self(authed_client, name, ver)

    # Make gateway request
    r1 = await authed_client.get(f"/api/rest/{name}/{ver}/status")
    # It may fail upstream; we only care it traversed /api/* path
    assert r1.status_code in (200, 400, 401, 404, 429, 500)

    # Fetch metrics
    m = await authed_client.get("/platform/monitor/metrics")
    assert m.status_code == 200
    body = m.json()
    series = body.get("response", {}).get("series") or body.get("series")
    assert isinstance(series, list)
    assert body.get("response", {}).get("total_requests") or body.get("total_requests") >= 1


@pytest.mark.asyncio
async def test_cors_strict_allows_localhost(monkeypatch, client):
    # Simulate wildcard origins + credentials with strict CORS enabled
    monkeypatch.setenv("CORS_STRICT", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("ALLOW_CREDENTIALS", "true")
    r = await client.get("/platform/monitor/liveness", headers={"Origin": "http://localhost:3000"})
    # CORS middleware should echo allowed origin
    assert r.headers.get("access-control-allow-origin") in ("http://localhost:3000", "http://localhost")


@pytest.mark.asyncio
async def test_csp_header_default_and_override(monkeypatch, client):
    # Default CSP should be present with strict directives
    monkeypatch.delenv("CONTENT_SECURITY_POLICY", raising=False)
    r = await client.get("/platform/monitor/liveness")
    assert r.status_code == 200
    csp = r.headers.get("Content-Security-Policy")
    assert csp and "default-src 'none'" in csp and "connect-src 'self'" in csp

    # Override via env var
    monkeypatch.setenv("CONTENT_SECURITY_POLICY", "default-src 'self'")
    r2 = await client.get("/platform/monitor/liveness")
    assert r2.headers.get("Content-Security-Policy") == "default-src 'self'"


@pytest.mark.asyncio
async def test_request_id_header_generation_and_echo(client):
    # Generated header
    r = await client.get("/platform/monitor/liveness")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")
    assert r.headers.get("request_id")
    # Echo incoming value
    incoming = "11111111-2222-3333-4444-555555555555"
    r2 = await client.get("/platform/monitor/liveness", headers={"X-Request-ID": incoming})
    assert r2.headers.get("X-Request-ID") == incoming
    assert r2.headers.get("request_id") == incoming


@pytest.mark.asyncio
async def test_memory_dump_and_restore(tmp_path, monkeypatch):
    # Ensure MEM mode and point dump path to tmp
    monkeypatch.setenv("MEM_OR_EXTERNAL", "MEM")
    dump_dir = tmp_path / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MEM_DUMP_PATH", str(dump_dir / "memory_dump.bin"))

    # Import utilities after env set
    from utils.memory_dump_util import dump_memory_to_file, find_latest_dump_path, restore_memory_from_file
    from utils.database import database

    # Seed some in-memory data
    database.db.users.insert_one({"username": "tmp", "email": "t@t.t", "password": "x"})
    path = dump_memory_to_file(None)
    assert os.path.exists(path)
    latest = find_latest_dump_path(str(dump_dir))
    assert latest and latest.endswith(".bin")
    # Wipe and restore
    database.db.users._docs.clear()
    assert database.db.users.count_documents({}) == 0
    info = restore_memory_from_file(latest)
    assert database.db.users.count_documents({}) >= 1
