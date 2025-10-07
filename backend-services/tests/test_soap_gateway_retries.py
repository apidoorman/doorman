import pytest


class _Resp:
    def __init__(self, status_code=200, body='<ok/>', headers=None):
        self.status_code = status_code
        self.text = body
        base = {'Content-Type': 'text/xml'}
        if headers:
            base.update(headers)
        self.headers = base
        self.content = (self.text or '').encode('utf-8')


def _mk_retry_xml_client(sequence, seen):
    counter = {'i': 0}

    class _Client:
        def __init__(self, timeout=None, limits=None, http2=False):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, content=None, params=None, headers=None):
            seen.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {}), 'content': content})
            idx = min(counter['i'], len(sequence) - 1)
            code = sequence[idx]
            counter['i'] = counter['i'] + 1
            return _Resp(code)
    return _Client


async def _setup_soap(client, name, ver, retry_count=0):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://soap.retry'],
        'api_type': 'REST',
        'api_allowed_retry_count': retry_count,
    }
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/call',
        'endpoint_description': 'soap call',
    })
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self
    await subscribe_self(client, name, ver)


@pytest.mark.asyncio
async def test_soap_retry_on_500_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'soapretry500', 'v1'
    await _setup_soap(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_xml_client([500, 200], seen))
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'application/xml'}, content='<env/>'
    )
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_soap_retry_on_502_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'soapretry502', 'v1'
    await _setup_soap(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_xml_client([502, 200], seen))
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'application/xml'}, content='<env/>'
    )
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_soap_retry_on_503_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'soapretry503', 'v1'
    await _setup_soap(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_xml_client([503, 200], seen))
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'application/xml'}, content='<env/>'
    )
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_soap_retry_on_504_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'soapretry504', 'v1'
    await _setup_soap(authed_client, name, ver, retry_count=2)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_xml_client([504, 200], seen))
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'application/xml'}, content='<env/>'
    )
    assert r.status_code == 200
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_soap_no_retry_when_retry_count_zero(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'soapretry0', 'v1'
    await _setup_soap(authed_client, name, ver, retry_count=0)
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_retry_xml_client([500, 200], seen))
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'application/xml'}, content='<env/>'
    )
    assert r.status_code == 500
    assert len(seen) == 1

