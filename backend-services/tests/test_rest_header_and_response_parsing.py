import pytest


class _Resp:
    def __init__(self, status_code=200, body=b'{"ok":true}', headers=None):
        self.status_code = status_code
        self._body = body
        base = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        if headers:
            base.update(headers)
        self.headers = base

    @property
    def content(self):
        return self._body

    @property
    def text(self):
        try:
            return self._body.decode('utf-8')
        except Exception:
            return ''

    def json(self):
        import json

        return json.loads(self.text)


def _mk_client_capture(seen, resp_status=200, resp_headers=None, resp_body=b'{"ok":true}'):
    class _Client:
        def __init__(self, timeout=None, limits=None, http2=False):
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
                return _Resp(405)

        async def post(self, url, json=None, params=None, headers=None, content=None, **kwargs):
            seen.append(
                {
                    'url': url,
                    'params': dict(params or {}),
                    'headers': dict(headers or {}),
                    'json': json,
                }
            )
            return _Resp(resp_status, body=resp_body, headers=resp_headers)

        async def get(self, url, **kwargs):
            seen.append({'url': url, 'params': {}, 'headers': {}})
            return _Resp(resp_status, body=resp_body, headers=resp_headers)

        async def put(self, url, **kwargs):
            seen.append({'url': url, 'params': {}, 'headers': {}})
            return _Resp(resp_status, body=resp_body, headers=resp_headers)

        async def delete(self, url, **kwargs):
            seen.append({'url': url, 'params': {}, 'headers': {}})
            return _Resp(resp_status, body=resp_body, headers=resp_headers)

    return _Client


async def _setup_api(client, name, ver, allowed_headers=None):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up.headers'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    if allowed_headers is not None:
        payload['api_allowed_headers'] = allowed_headers
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/p',
            'endpoint_description': 'p',
        },
    )
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self

    await subscribe_self(client, name, ver)


@pytest.mark.asyncio
async def test_header_allowlist_forwards_only_allowed_headers_case_insensitive(
    monkeypatch, authed_client
):
    import services.gateway_service as gs

    name, ver = 'hdrallow', 'v1'
    await _setup_api(authed_client, name, ver, allowed_headers=['X-Custom', 'Content-Type'])
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_client_capture(seen))
    r = await authed_client.post(
        f'/api/rest/{name}/{ver}/p?foo=bar',
        headers={'x-custom': 'abc', 'X-Blocked': 'nope', 'Content-Type': 'application/json'},
        json={'a': 1},
    )
    assert r.status_code == 200
    assert len(seen) == 1
    forwarded = seen[0]['headers']
    keys_lower = {k.lower(): v for k, v in forwarded.items()}
    assert keys_lower.get('x-custom') == 'abc'
    assert 'x-blocked' not in keys_lower


@pytest.mark.asyncio
async def test_header_block_non_allowlisted_headers(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'hdrblock', 'v1'
    await _setup_api(authed_client, name, ver, allowed_headers=['Content-Type'])
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_client_capture(seen))
    r = await authed_client.post(
        f'/api/rest/{name}/{ver}/p',
        headers={'X-NotAllowed': '123', 'Content-Type': 'application/json'},
        json={'a': 1},
    )
    assert r.status_code == 200
    forwarded = seen[0]['headers']
    assert 'X-NotAllowed' not in forwarded and 'x-notallowed' not in {k.lower() for k in forwarded}


def test_response_parse_application_json():
    import services.gateway_service as gs

    body = b'{"x": 1}'
    resp = _Resp(headers={'Content-Type': 'application/json'}, body=body)
    out = gs.GatewayService.parse_response(resp)
    assert isinstance(out, dict) and out.get('x') == 1


def test_response_parse_text_plain_fallback():
    import services.gateway_service as gs

    body = b'hello world'
    resp = _Resp(headers={'Content-Type': 'text/plain'}, body=body)
    out = gs.GatewayService.parse_response(resp)
    assert out == body


def test_response_parse_application_xml():
    import services.gateway_service as gs

    body = b'<root><x>1</x></root>'
    resp = _Resp(headers={'Content-Type': 'application/xml'}, body=body)
    out = gs.GatewayService.parse_response(resp)
    from xml.etree.ElementTree import Element

    assert isinstance(out, Element) and out.tag == 'root'


def test_response_parse_malformed_json_as_text():
    import services.gateway_service as gs

    body = b'{"x": 1'
    resp = _Resp(headers={'Content-Type': 'text/plain'}, body=body)
    out = gs.GatewayService.parse_response(resp)
    assert out == body


def test_response_binary_passthrough_no_decode():
    import services.gateway_service as gs

    binary = b'\x00\xff\x10\x80'
    resp = _Resp(headers={'Content-Type': 'application/octet-stream'}, body=binary)
    out = gs.GatewayService.parse_response(resp)
    assert out == binary


def test_response_malformed_json_with_application_json_raises():
    import services.gateway_service as gs

    body = b'{"x": 1'
    resp = _Resp(headers={'Content-Type': 'application/json'}, body=body)
    import pytest

    with pytest.raises(Exception):
        gs.GatewayService.parse_response(resp)


@pytest.mark.asyncio
async def test_rest_gateway_returns_500_on_malformed_json_upstream(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'jsonfail', 'v1'
    await _setup_api(authed_client, name, ver)

    bad_body = b'{"x": 1'

    class _Resp2:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'application/json'}
            self.content = bad_body
            self.text = bad_body.decode('utf-8', errors='ignore')

        def json(self):
            import json

            return json.loads(self.text)

    class _Client2:
        def __init__(self, *a, **k):
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
                return _Resp2()

        async def get(self, url, params=None, headers=None, **kwargs):
            return _Resp2()

        async def post(self, url, json=None, params=None, headers=None, content=None, **kwargs):
            return _Resp2()

        async def head(self, url, params=None, headers=None, **kwargs):
            return _Resp2()

        async def put(self, url, **kwargs):
            return _Resp2()

        async def delete(self, url, **kwargs):
            return _Resp2()

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _Client2)

    r = await authed_client.post(
        f'/api/rest/{name}/{ver}/p', headers={'Content-Type': 'application/json'}, json={'k': 'v'}
    )
    assert r.status_code == 500
    body = r.json()
    payload = body.get('response', body)
    assert payload.get('error_code') or payload.get('error_message')
