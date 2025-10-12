import httpx
import pytest


@pytest.mark.asyncio
async def test_request_id_propagates_to_upstream_and_response(monkeypatch, authed_client):
    # Prepare a mock upstream that captures X-Request-ID and echoes it back
    captured = {'xrid': None}

    def handler(req: httpx.Request) -> httpx.Response:
        captured['xrid'] = req.headers.get('X-Request-ID')
        return httpx.Response(200, json={'ok': True}, headers={'X-Upstream-Request-ID': captured['xrid'] or ''})

    transport = httpx.MockTransport(handler)
    mock_client = httpx.AsyncClient(transport=transport)

    # Monkeypatch gateway's HTTP client factory to use our mock client
    from services import gateway_service

    async def _get_client():
        return mock_client

    # Patch classmethod to return our instance
    monkeypatch.setattr(gateway_service.GatewayService, 'get_http_client', classmethod(lambda cls: mock_client))

    # Create an API + endpoint that allows forwarding back X-Upstream-Request-ID
    api_name, api_version = 'ridtest', 'v1'
    # Allow the upstream echoed header to pass through to response
    payload = {
        'api_name': api_name,
        'api_version': api_version,
        'api_description': f'{api_name} {api_version}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_allowed_headers': ['X-Upstream-Request-ID'],
    }
    r = await authed_client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text

    r2 = await authed_client.post('/platform/endpoint', json={
        'api_name': api_name,
        'api_version': api_version,
        'endpoint_method': 'GET',
        'endpoint_uri': '/echo',
        'endpoint_description': 'echo'
    })
    assert r2.status_code in (200, 201), r2.text

    # Subscribe the caller to the API to satisfy gateway subscription requirements
    sub = await authed_client.post('/platform/subscription/subscribe', json={'username': 'admin', 'api_name': api_name, 'api_version': api_version})
    assert sub.status_code in (200, 201), sub.text

    # Make gateway request
    resp = await authed_client.get(f'/api/rest/{api_name}/{api_version}/echo')
    assert resp.status_code == 200, resp.text

    # Response must include X-Request-ID (set by middleware)
    rid = resp.headers.get('X-Request-ID')
    assert rid, 'Missing X-Request-ID in response'

    # Upstream must have received same X-Request-ID
    assert captured['xrid'] == rid

    # Response should expose upstream echoed header through allowed headers
    assert resp.headers.get('X-Upstream-Request-ID') == rid
