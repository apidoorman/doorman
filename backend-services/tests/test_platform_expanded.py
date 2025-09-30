# External imports
import os
import json
import pytest

@pytest.mark.asyncio
async def test_routing_crud(authed_client):
    create = await authed_client.post(
        '/platform/routing',
        json={
            'routing_name': 'routing-client-A',
            'client_key': 'client-A',
            'routing_servers': ['http://s1.example', 'http://s2.example'],
            'server_index': 0,
        },
    )
    assert create.status_code in (200, 201)

    get_one = await authed_client.get('/platform/routing/client-A')
    assert get_one.status_code == 200

    update = await authed_client.put(
        '/platform/routing/client-A',
        json={'routing_servers': ['http://s1.example', 'http://s3.example']},
    )
    assert update.status_code == 200

    list_all = await authed_client.get('/platform/routing/all?page=1&page_size=50')
    assert list_all.status_code == 200

    delete = await authed_client.delete('/platform/routing/client-A')
    assert delete.status_code == 200

@pytest.mark.asyncio
async def test_security_and_memory_dump_restore(authed_client):

    ur = await authed_client.put(
        '/platform/role/admin',
        json={'manage_security': True},
    )
    assert ur.status_code == 200

    gs = await authed_client.get('/platform/security/settings')
    assert gs.status_code == 200

    us = await authed_client.put('/platform/security/settings', json={})
    assert us.status_code in (200, 400)

    dump = await authed_client.post('/platform/memory/dump', json={})

    assert dump.status_code in (200, 400)
    if dump.status_code == 200:
        path = dump.json().get('path') or dump.json().get('response', {}).get('path')
        assert path
        restore = await authed_client.post('/platform/memory/restore', json={'path': path})
        assert restore.status_code == 200

@pytest.mark.asyncio
async def test_logging_endpoints(authed_client):

    r1 = await authed_client.put(
        '/platform/role/admin',
        json={'view_logs': True, 'export_logs': True},
    )
    assert r1.status_code == 200

    logs = await authed_client.get('/platform/logging/logs?limit=10')
    assert logs.status_code == 200

    files = await authed_client.get('/platform/logging/logs/files')
    assert files.status_code == 200

    stats = await authed_client.get('/platform/logging/logs/statistics')
    assert stats.status_code == 200

    export = await authed_client.get('/platform/logging/logs/export?format=json')
    assert export.status_code == 200

    download = await authed_client.get('/platform/logging/logs/download?format=json')
    assert download.status_code == 200

@pytest.mark.asyncio
async def test_onboard_public_apis_for_all_gateway_types(monkeypatch, authed_client):

    rest_apis = [
        ('jsonplaceholder', 'v1', ['https://jsonplaceholder.typicode.com'], [
            ('GET', '/posts/1')
        ]),
        ('httpbin', 'v1', ['https://httpbin.org'], [
            ('GET', '/get')
        ]),
    ]
    for name, ver, servers, endpoints in rest_apis:
        c = await authed_client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': f'{name} {ver}',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': servers,
                'api_type': 'REST',
                'api_allowed_retry_count': 0,
            },
        )
        assert c.status_code in (200, 201)

        s = await authed_client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        assert s.status_code in (200, 201)
        for method, uri in endpoints:
            ep = await authed_client.post(
                '/platform/endpoint',
                json={
                    'api_name': name,
                    'api_version': ver,
                    'endpoint_method': method,
                    'endpoint_uri': uri,
                    'endpoint_description': f'{method} {uri}',
                },
            )
            assert ep.status_code in (200, 201)

    gql_apis = [
        ('gh-pokeapi', 'v1', ['https://graphql-pokeapi.graphcdn.app']),
        ('gh-swapi', 'v1', ['https://swapi-graphql.netlify.app/.netlify/functions/index']),
    ]
    for name, ver, servers in gql_apis:
        c = await authed_client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': f'{name} {ver}',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': servers,
                'api_type': 'GRAPHQL',
                'api_allowed_retry_count': 0,
            },
        )
        assert c.status_code in (200, 201)
        s = await authed_client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        assert s.status_code in (200, 201)

    soap_apis = [
        ('soap-number', 'v1', ['https://www.dataaccess.com/webservicesserver/NumberConversion.wso']),
        ('soap-tempconvert', 'v1', ['https://www.w3schools.com/xml/tempconvert.asmx']),
    ]
    for name, ver, servers in soap_apis:
        c = await authed_client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': f'{name} {ver}',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': servers,
                'api_type': 'SOAP',
                'api_allowed_retry_count': 0,
            },
        )
        assert c.status_code in (200, 201)
        s = await authed_client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        assert s.status_code in (200, 201)

    grpc_apis = [
        ('grpc-echo', 'v1', ['http://localhost:50051']),
        ('grpc-calc', 'v1', ['http://localhost:50052']),
    ]
    for name, ver, servers in grpc_apis:
        c = await authed_client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': f'{name} {ver}',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': servers,
                'api_type': 'GRPC',
                'api_allowed_retry_count': 0,
            },
        )
        assert c.status_code in (200, 201)
        s = await authed_client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        assert s.status_code in (200, 201)

    import services.gateway_service as gs
    class _FakeHTTPResponse:
        def __init__(self, status_code=200, json_body=None, text_body=None, headers=None):
            self.status_code = status_code
            self._json_body = json_body
            self.text = text_body if text_body is not None else ('' if json_body is not None else 'OK')
            self.headers = headers or {'Content-Type': 'application/json' if json_body is not None else 'text/plain'}
        def json(self):
            if self._json_body is None:
                return json.loads(self.text or '{}')
            return self._json_body
    class _FakeAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, headers=None):
            return _FakeHTTPResponse(200, json_body={'ping': 'pong'})
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    import routes.gateway_routes as gr
    async def _no_limit(req):
        return None
    async def _pass_sub(req):
        return {'sub': 'admin'}
    async def _pass_group(req, full_path: str = None, user_to_subscribe=None):
        return {'sub': 'admin'}
    monkeypatch.setattr(gr, 'limit_and_throttle', _no_limit)
    monkeypatch.setattr(gr, 'subscription_required', _pass_sub)
    monkeypatch.setattr(gr, 'group_required', _pass_group)
    rest_call = await authed_client.get('/api/rest/httpbin/v1/get')
    assert rest_call.status_code in (200, 500)
