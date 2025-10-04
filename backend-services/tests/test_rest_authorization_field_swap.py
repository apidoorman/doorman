import pytest


class _Resp:
    def __init__(self, status_code=200, json_body=None, headers=None):
        self.status_code = status_code
        self._json_body = json_body
        base_headers = {'Content-Type': 'application/json'}
        if headers:
            base_headers.update(headers)
        self.headers = base_headers
        self.text = ''
    def json(self):
        return self._json_body


def _mk_client_capture(seen):
    class _Client:
        def __init__(self, timeout=None):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, params=None, headers=None, content=None):
            payload = {'method': 'POST', 'url': url, 'params': dict(params or {}), 'body': json, 'headers': headers or {}}
            seen.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {}), 'json': json})
            return _Resp(200, json_body=payload, headers={'X-Upstream': 'yes'})
        async def get(self, url, params=None, headers=None):
            payload = {'method': 'GET', 'url': url, 'params': dict(params or {}), 'headers': headers or {}}
            seen.append({'url': url, 'params': dict(params or {}), 'headers': dict(headers or {})})
            return _Resp(200, json_body=payload, headers={'X-Upstream': 'yes'})
    return _Client


async def _setup_api(client, name, ver, swap_header, allowed_headers=None):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up.authswap'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_authorization_field_swap': swap_header,
    }
    if allowed_headers is not None:
        payload['api_allowed_headers'] = allowed_headers
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'GET',
        'endpoint_uri': '/p',
        'endpoint_description': 'p'
    })
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self
    await subscribe_self(client, name, ver)


@pytest.mark.asyncio
async def test_auth_swap_injects_authorization_from_custom_header(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'authswap1', 'v1'
    swap_from = 'x-token'
    await _setup_api(authed_client, name, ver, swap_from, allowed_headers=['authorization', swap_from])
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_client_capture(seen))
    r = await authed_client.get(
        f'/api/rest/{name}/{ver}/p',
            headers={swap_from: 'Bearer backend-token'}
    )
    assert r.status_code == 200
    assert len(seen) == 1
    forwarded = (r.json() or {}).get('headers') or {}
    auth_val = forwarded.get('Authorization') or forwarded.get('authorization')
    assert auth_val == 'Bearer backend-token'


@pytest.mark.asyncio
async def test_auth_swap_missing_source_header_no_crash(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'authswap2', 'v1'
    swap_from = 'X-Backend-Auth'
    await _setup_api(authed_client, name, ver, swap_from, allowed_headers=['Content-Type', swap_from])
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_client_capture(seen))
    r = await authed_client.get(
        f'/api/rest/{name}/{ver}/p',
        headers={}
    )
    assert r.status_code == 200
    fwd = (r.json() or {}).get('headers') or {}
    # Authorization should not be injected if source header is missing
    assert not (('Authorization' in fwd) or ('authorization' in fwd))


@pytest.mark.asyncio
async def test_auth_swap_with_empty_value_does_not_override(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'authswap3', 'v1'
    swap_from = 'X-Backend-Auth'
    await _setup_api(authed_client, name, ver, swap_from, allowed_headers=['Content-Type', swap_from, 'Authorization'])
    seen = []
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _mk_client_capture(seen))
    # Provide normal Authorization but empty backend header; should keep existing Authorization
    r = await authed_client.get(
        f'/api/rest/{name}/{ver}/p',
        headers={swap_from: '', 'Authorization': 'Bearer existing'}
    )
    assert r.status_code == 200
    fwd = (r.json() or {}).get('headers') or {}
    auth_val = fwd.get('Authorization') or fwd.get('authorization')
    assert auth_val == 'Bearer existing'
