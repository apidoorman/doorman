import os

import pytest


@pytest.mark.asyncio
async def test_memory_dump_requires_key_then_succeeds(monkeypatch, authed_client, tmp_path):
    monkeypatch.delenv('MEM_ENCRYPTION_KEY', raising=False)
    r1 = await authed_client.post('/platform/memory/dump')
    assert r1.status_code == 400
    assert (r1.json().get('error_code') or r1.json().get('response', {}).get('error_code')) in (
        'MEM002',
        'MEM002',
    )

    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'route-key-123456')
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'r' / 'dump.bin'))
    r2 = await authed_client.post('/platform/memory/dump')
    assert r2.status_code == 200, r2.text
    body = r2.json()
    path = body.get('response', {}).get('path') or body.get('path')
    assert path and path.endswith('.bin')


@pytest.mark.asyncio
async def test_memory_restore_404_missing(monkeypatch, authed_client, tmp_path):
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'route-key-987654')
    r = await authed_client.post(
        '/platform/memory/restore', json={'path': str(tmp_path / 'nope.bin')}
    )
    assert r.status_code == 404
    data = r.json()
    assert (
        data.get('error_code') == 'MEM003' or data.get('response', {}).get('error_code') == 'MEM003'
    )


@pytest.mark.asyncio
async def test_memory_dump_then_restore_flow(monkeypatch, authed_client, tmp_path):
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'route-key-abcdef')
    monkeypatch.setenv('MEM_DUMP_PATH', str(tmp_path / 'd' / 'dump.bin'))

    create = await authed_client.post(
        '/platform/user',
        json={
            'username': 'e2euser',
            'email': 'e2e@example.com',
            'password': 'VeryStrongPassword123!',
            'role': 'admin',
            'groups': ['ALL'],
        },
    )
    assert create.status_code in (200, 201), create.text

    d = await authed_client.post(
        '/platform/memory/dump', json={'path': str(tmp_path / 'd' / 'dump.bin')}
    )
    assert d.status_code == 200
    dump_body = d.json()
    dump_path = dump_body.get('response', {}).get('path') or dump_body.get('path')
    assert dump_path and os.path.exists(dump_path)

    delete = await authed_client.delete('/platform/user/e2euser')
    assert delete.status_code in (200, 204)

    r = await authed_client.post('/platform/memory/restore', json={'path': dump_path})
    assert r.status_code == 200, r.text

    check = await authed_client.get('/platform/user/e2euser')
    assert check.status_code == 200


@pytest.mark.asyncio
async def test_cors_wildcard_without_credentials_allows(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'false')
    monkeypatch.setenv('CORS_STRICT', 'false')
    body = {'origin': 'http://any-origin', 'method': 'GET'}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('actual', {}).get('allowed') is True


@pytest.mark.asyncio
async def test_cors_wildcard_with_credentials_strict_blocks(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'true')
    body = {'origin': 'http://example.com', 'method': 'GET', 'with_credentials': True}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('actual', {}).get('allowed') is False


@pytest.mark.asyncio
async def test_cors_checker_implicitly_allows_options(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOW_METHODS', 'GET,POST')
    body = {'origin': 'http://localhost:3000', 'method': 'OPTIONS'}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    assert (
        r.json()
        .get('preflight', {})
        .get('response_headers', {})
        .get('Access-Control-Allow-Methods')
    )


@pytest.mark.asyncio
async def test_cors_headers_case_insensitive(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOW_HEADERS', 'Content-Type,Authorization')
    body = {
        'origin': 'http://localhost:3000',
        'method': 'GET',
        'request_headers': ['content-type', 'authorization'],
    }
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('preflight', {}).get('allowed') is True


@pytest.mark.asyncio
async def test_cors_checker_vary_origin_present(monkeypatch, authed_client):
    body = {'origin': 'http://localhost:3000', 'method': 'GET'}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    pre = data.get('preflight', {}).get('response_headers', {})
    actual = data.get('actual', {}).get('response_headers', {})
    assert pre.get('Vary') == 'Origin' and actual.get('Vary') == 'Origin'


@pytest.mark.asyncio
async def test_cors_checker_disallows_unknown_origin(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://localhost:3000')
    body = {'origin': 'http://evil', 'method': 'GET'}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    assert r.json().get('actual', {}).get('allowed') is False
