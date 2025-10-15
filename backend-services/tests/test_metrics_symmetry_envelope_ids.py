import json
import re
import pytest

@pytest.mark.asyncio
async def test_metrics_bytes_in_uses_content_length(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'msym', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/echo')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs
    resp_body = b'{"ok":true,"pad":"' + b'Z' * 15 + b'"}'

    class _FakeHTTPResponse:
        def __init__(self, status_code=200, body=resp_body):
            self.status_code = status_code
            self.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
            self.text = body.decode('utf-8')
            self.content = body
        def json(self):
            return json.loads(self.text)

    class _FakeAsyncClient:
        def __init__(self, timeout=None, limits=None, http2=False): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
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
                return _FakeHTTPResponse(405)
        async def get(self, url, **kwargs): return _FakeHTTPResponse(200)
        async def post(self, url, data=None, json=None, headers=None, params=None, **kwargs): return _FakeHTTPResponse(200)
        async def put(self, url, **kwargs): return _FakeHTTPResponse(200)
        async def delete(self, url, **kwargs): return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    m0 = await authed_client.get('/platform/monitor/metrics')
    j0 = m0.json().get('response') or m0.json()
    tin0 = int(j0.get('total_bytes_in', 0))
    tout0 = int(j0.get('total_bytes_out', 0))

    payload = '"' + ('X' * 23) + '"'
    headers = {'Content-Type': 'application/json', 'Content-Length': str(len(payload))}
    r = await authed_client.post(f'/api/rest/{name}/{ver}/echo', headers=headers, content=payload)
    assert r.status_code == 200

    m1 = await authed_client.get('/platform/monitor/metrics')
    j1 = m1.json().get('response') or m1.json()
    tin1 = int(j1.get('total_bytes_in', 0))
    tout1 = int(j1.get('total_bytes_out', 0))

    assert tin1 - tin0 >= len(payload)
    assert tout1 - tout0 >= len(resp_body)

@pytest.mark.asyncio
async def test_response_envelope_for_non_json_error(monkeypatch, client):
    monkeypatch.setenv('MAX_BODY_SIZE_BYTES', '10')

    payload = 'x' * 100
    r = await client.post('/platform/authorization', content=payload, headers={'Content-Type': 'text/plain'})
    assert r.status_code == 413
    assert r.headers.get('content-type', '').lower().startswith('application/json')
    body = r.json()
    err_code = body.get('error_code') or (body.get('response') or {}).get('error_code')
    assert err_code == 'REQ001'
    msg = body.get('error_message') or (body.get('response') or {}).get('error_message')
    assert isinstance(msg, str) and msg

def _get_operation_id(spec: dict, path: str, method: str) -> str:
    return spec['paths'][path][method.lower()]['operationId']

def test_unique_route_ids_are_stable():
    from doorman import doorman as app
    spec1 = app.openapi()
    spec2 = app.openapi()

    pairs = [
        ('/platform/authorization', 'post'),
        ('/platform/monitor/liveness', 'get'),
        ('/api/status', 'get'),
    ]
    for p, m in pairs:
        op1 = _get_operation_id(spec1, p, m)
        op2 = _get_operation_id(spec2, p, m)
        assert isinstance(op1, str) and isinstance(op2, str)
        assert op1 == op2
        assert op1 == op1.lower()
        assert re.search(r'[a-z0-9_]+', op1)
