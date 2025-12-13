import pytest


@pytest.mark.asyncio
async def test_grpc_server_streaming(monkeypatch, authed_client):
    name, ver = 'gstr', 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:50051'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    r = await authed_client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/grpc',
            'endpoint_description': 'grpc',
        },
    )
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self

    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    # Fake pb2 modules
    def _imp(n):
        if n.endswith('_pb2'):
            mod = type('PB2', (), {})
            mod.MRequest = type('Req', (), {})

            class Reply:
                DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()

                def __init__(self, ok=True):
                    self.ok = ok

                @staticmethod
                def FromString(b):
                    return Reply(True)

            mod.MReply = Reply
            return mod
        if n.endswith('_pb2_grpc'):

            class Stub:
                def __init__(self, ch):
                    pass

            return type('SVC', (), {'SvcStub': Stub})
        raise ImportError(n)

    monkeypatch.setattr(gs.importlib, 'import_module', _imp)

    class Chan:
        def unary_stream(self, method, request_serializer=None, response_deserializer=None):
            async def _aiter(req, metadata=None):
                class Msg:
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                    ok = True

                for _ in range(2):
                    yield Msg()

            return _aiter

    class _Aio:
        @staticmethod
        def insecure_channel(url):
            return Chan()

    monkeypatch.setattr(
        gs,
        'grpc',
        type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}),
    )

    body = {'method': 'Svc.M', 'message': {}, 'stream': 'server', 'max_items': 2}
    resp = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json=body,
    )
    assert resp.status_code == 200
    data = resp.json().get('response') or resp.json()
    assert isinstance(data.get('items'), list) and len(data['items']) == 2


@pytest.mark.asyncio
async def test_grpc_metadata_pass_through(monkeypatch, authed_client):
    name, ver = 'gmeta', 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:50051'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_allowed_headers': ['X-Meta-One'],
    }
    r = await authed_client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/grpc',
            'endpoint_description': 'grpc',
        },
    )
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self

    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    def _imp(n):
        if n.endswith('_pb2'):
            mod = type('PB2', (), {})
            mod.MRequest = type('Req', (), {})

            class Reply:
                DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()

                @staticmethod
                def FromString(b):
                    return Reply()

            mod.MReply = Reply
            return mod
        if n.endswith('_pb2_grpc'):

            class Stub:
                def __init__(self, ch):
                    pass

            return type('SVC', (), {'SvcStub': Stub})
        raise ImportError(n)

    monkeypatch.setattr(gs.importlib, 'import_module', _imp)

    captured = {'md': None}

    class Chan:
        def unary_unary(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req, metadata=None):
                captured['md'] = list(metadata or [])

                class Reply:
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                    ok = True

                return Reply()

            return _call

    class _Aio:
        @staticmethod
        def insecure_channel(url):
            return Chan()

    monkeypatch.setattr(
        gs,
        'grpc',
        type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}),
    )

    headers = {'X-API-Version': ver, 'Content-Type': 'application/json', 'X-Meta-One': 'alpha'}
    r = await authed_client.post(
        f'/api/grpc/{name}', headers=headers, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 200
    assert ('x-meta-one', 'alpha') in [(k.lower(), v) for k, v in (captured['md'] or [])]
