import pytest


class _FakeXMLResponse:
    def __init__(self, status_code=200, text='<ok/>', headers=None):
        self.status_code = status_code
        self.text = text
        base = {'Content-Type': 'text/xml'}
        if headers:
            base.update(headers)
        self.headers = base
        self.content = self.text.encode('utf-8')


def _mk_xml_client(captured):
    class _FakeXMLClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, **kwargs):
            """Generic request method used by http_client.request_with_resilience"""
            method = method.upper()
            if method == 'GET':
                return await self.get(url, **kwargs)
            elif method == 'POST':
                return await self.post(url, **kwargs)
            elif method == 'PUT':
                return await self.put(url, **kwargs)
            elif method == 'DELETE':
                return await self.delete(url, **kwargs)
            elif method == 'HEAD':
                return await self.get(url, **kwargs)
            elif method == 'PATCH':
                return await self.put(url, **kwargs)
            else:
                return _FakeXMLResponse(405, '<error>Method not allowed</error>')

        async def get(self, url, **kwargs):
            return _FakeXMLResponse(200, '<ok/>', {'X-Upstream': 'yes', 'Content-Type': 'text/xml'})

        async def post(self, url, content=None, params=None, headers=None, **kwargs):
            captured.append({'url': url, 'headers': dict(headers or {}), 'content': content})
            return _FakeXMLResponse(200, '<ok/>', {'X-Upstream': 'yes', 'Content-Type': 'text/xml'})

        async def put(self, url, **kwargs):
            return _FakeXMLResponse(200, '<ok/>', {'X-Upstream': 'yes', 'Content-Type': 'text/xml'})

        async def delete(self, url, **kwargs):
            return _FakeXMLResponse(200, '<ok/>', {'X-Upstream': 'yes', 'Content-Type': 'text/xml'})

    return _FakeXMLClient


async def _setup_api(client, name, ver):
    r = await client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://soap.up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    assert r.status_code in (200, 201)
    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/call',
            'endpoint_description': 'soap call',
        },
    )
    assert r2.status_code in (200, 201)
    rme = await client.get('/platform/user/me')
    username = rme.json().get('username') if rme.status_code == 200 else 'admin'
    rs = await client.post(
        '/platform/subscription/subscribe',
        json={'username': username, 'api_name': name, 'api_version': ver},
    )
    assert rs.status_code in (200, 201)


@pytest.mark.asyncio
async def test_soap_incoming_application_xml_sets_text_xml_outgoing(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'soapct1', 'v1'
    await _setup_api(authed_client, name, ver)
    captured = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_xml_client(captured))
    envelope = '<Envelope/>'
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call',
        headers={'Content-Type': 'application/xml'},
        content=envelope,
    )
    assert r.status_code == 200
    assert len(captured) == 1
    h = captured[0]['headers']
    assert h.get('Content-Type') == 'text/xml; charset=utf-8'


@pytest.mark.asyncio
async def test_soap_incoming_text_xml_passes_through(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'soapct2', 'v1'
    await _setup_api(authed_client, name, ver)
    captured = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_xml_client(captured))
    envelope = '<Envelope/>'
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'text/xml'}, content=envelope
    )
    assert r.status_code == 200
    h = captured[0]['headers']
    assert h.get('Content-Type') == 'text/xml'


@pytest.mark.asyncio
async def test_soap_incoming_application_soap_xml_passes_through(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'soapct3', 'v1'
    await _setup_api(authed_client, name, ver)
    captured = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_xml_client(captured))
    envelope = '<Envelope/>'
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call',
        headers={'Content-Type': 'application/soap+xml'},
        content=envelope,
    )
    assert r.status_code == 200
    h = captured[0]['headers']
    assert h.get('Content-Type') == 'application/soap+xml'


@pytest.mark.asyncio
async def test_soap_adds_default_soapaction_when_missing(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'soapct4', 'v1'
    await _setup_api(authed_client, name, ver)
    captured = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_xml_client(captured))
    envelope = '<Envelope/>'
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call',
        headers={'Content-Type': 'application/xml'},
        content=envelope,
    )
    assert r.status_code == 200
    h = captured[0]['headers']
    assert 'SOAPAction' in h and h['SOAPAction'] == '""'


@pytest.mark.asyncio
async def test_soap_parses_xml_response_success(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'soapct5', 'v1'
    await _setup_api(authed_client, name, ver)
    captured = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_xml_client(captured))
    envelope = '<Envelope/>'
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call',
        headers={'Content-Type': 'application/xml'},
        content=envelope,
    )
    assert r.status_code == 200
    assert '<ok/>' in (r.text or '')


@pytest.mark.asyncio
async def test_soap_auto_allows_common_request_headers(monkeypatch, authed_client):
    """Accept and User-Agent should be forwarded for SOAP without manual allow-listing."""
    import services.gateway_service as gs

    name, ver = 'soapct6', 'v1'
    await _setup_api(authed_client, name, ver)
    captured = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_xml_client(captured))
    envelope = '<Envelope/>'
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call',
        headers={
            'Content-Type': 'application/xml',
            'Accept': 'text/xml',
            'User-Agent': 'doorman-tests/1.0',
        },
        content=envelope,
    )
    assert r.status_code == 200
    assert len(captured) == 1
    h = {k.lower(): v for k, v in (captured[0]['headers'] or {}).items()}
    # Content-Type adjusted for SOAP
    assert h.get('content-type') in ('text/xml; charset=utf-8', 'text/xml', 'application/soap+xml')
    # Auto-allowed common SOAP request headers
    assert h.get('accept') == 'text/xml'
    assert h.get('user-agent') == 'doorman-tests/1.0'
    # SOAPAction auto-added
    assert 'soapaction' in h
