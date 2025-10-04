import pytest


class _Resp:
    def __init__(self, status_code=200, body=b'{"ok":true}', headers=None):
        self.status_code = status_code
        self._body = body
        self.text = body.decode('utf-8')
        base = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        if headers:
            base.update(headers)
        self.headers = base

    def json(self):
        import json
        return json.loads(self.text)


def _mk_retry_client(sequence, seen):
    """Factory for a fake AsyncClient that returns statuses from `sequence`.
    Records each call's (url, headers, params) into `seen` list.
    """

    counter = {'i': 0}

    class _Client:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, params=None, headers=None, content=None):
            seen.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {}), 'json': json})
            idx = min(counter['i'], len(sequence) - 1)
            code = sequence[idx]
            counter['i'] = counter['i'] + 1
            return _Resp(code)

        async def get(self, url, params=None, headers=None):
            seen.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {})})
            idx = min(counter['i'], len(sequence) - 1)
            code = sequence[idx]
            counter['i'] = counter['i'] + 1
            return _Resp(code)

    return _Client


async def _setup_api(client, name, ver, retry_count=0, allowed_headers=None):
    # Create API with custom retry count and allowed headers
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up.retry'],
        'api_type': 'REST',
        'api_allowed_retry_count': retry_count,
    }
    if allowed_headers is not None:
        payload['api_allowed_headers'] = allowed_headers
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/p',
        'endpoint_description': 'p'
    })
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self
    await subscribe_self(client, name, ver)


@pytest.mark.asyncio
async def test_rest_retry_on_500_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retry500', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([500, 200], seen))
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', json={'a': 1})
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_rest_retry_on_502_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retry502', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([502, 200], seen))
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', json={'a': 1})
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_rest_retry_on_503_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retry503', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([503, 200], seen))
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', json={'a': 1})
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_rest_retry_on_504_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retry504', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([504, 200], seen))
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', json={'a': 1})
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_rest_no_retry_when_retry_count_zero(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retry0', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=0)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([500, 200], seen))
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', json={'a': 1})
    assert r.status_code == 500
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_rest_retry_stops_after_limit(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retryLimit', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=1)
    seen = []
    # Always fail: expect one retry then return failure
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([500, 500, 200], seen))
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', json={'a': 1})
    assert r.status_code == 500
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_rest_retry_preserves_headers_and_params(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'retryHdr', 'v1'
    await _setup_api(authed_client, name, ver, retry_count=1, allowed_headers=['X-Custom'])
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_client([500, 200], seen))
    r = await authed_client.post(
        f'/api/rest/{name}/{ver}/p?foo=bar',
        headers={'X-Custom': 'abc', 'Content-Type': 'application/json'},
        json={'a': 1}
    )
    assert r.status_code == 200
    assert len(seen) == 2
    # Both attempts should include the same header and params
    assert all(call['params'].get('foo') == 'bar' for call in seen)
    def _hdr(call):
        return call['headers'].get('X-Custom') or call['headers'].get('x-custom')
    assert all(_hdr(call) == 'abc' for call in seen)
