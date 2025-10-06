import pytest


async def _setup_api(client, name, ver):
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
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/grpc',
        'endpoint_description': 'grpc',
    })
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self
    await subscribe_self(client, name, ver)


def _fake_import(grpc_module_name: str):
    def _imp(n):
        if n.endswith('_pb2'):
            mod = type('PB2', (), {})
            setattr(mod, 'MRequest', type('Req', (), {}))
            class Reply:
                DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                def __init__(self, ok=True): self.ok = ok
                @staticmethod
                def FromString(b): return Reply(True)
            setattr(mod, 'MReply', Reply)
            return mod
        if n.endswith('_pb2_grpc'):
            class Stub: 
                def __init__(self, ch): pass
            return type('SVC', (), {'SvcStub': Stub})
        raise ImportError(n)
    return _imp


@pytest.mark.asyncio
async def test_grpc_client_streaming(monkeypatch, authed_client):
    name, ver = 'gclstr', 'v1'
    await _setup_api(authed_client, name, ver)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.importlib, 'import_module', _fake_import('gs'))

    class Chan:
        def stream_unary(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req_iter, metadata=None):
                # Consume iterator
                count = 0
                async for _ in req_iter:
                    count += 1
                class Reply:
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                    ok = True
                return Reply()
            return _call
    class _Aio:
        @staticmethod
        def insecure_channel(url): return Chan()
    monkeypatch.setattr(gs, 'grpc', type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}))

    body = {'method': 'Svc.M', 'message': {}, 'stream': 'client', 'messages': [{}, {}, {}]}
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json=body)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_grpc_client_streaming_field_mapping(monkeypatch, authed_client):
    name, ver = 'gclmap', 'v1'
    await _setup_api(authed_client, name, ver)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.importlib, 'import_module', _fake_import('gs'))

    class Chan:
        def stream_unary(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req_iter, metadata=None):
                total = 0
                async for req in req_iter:
                    try:
                        total += int(getattr(req, 'val', 0))
                    except Exception:
                        pass
                class Reply:
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'sum'})()]})()
                    def __init__(self, sum): self.sum = sum
                return Reply(total)
            return _call
    class _Aio:
        @staticmethod
        def insecure_channel(url): return Chan()
    monkeypatch.setattr(gs, 'grpc', type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}))

    msgs = [{'val': 1}, {'val': 2}, {'val': 3}]
    body = {'method': 'Svc.M', 'message': {}, 'stream': 'client', 'messages': msgs}
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json=body)
    assert r.status_code == 200
    data = r.json().get('response') or r.json()
    assert int(data.get('sum', 0)) == 6


@pytest.mark.asyncio
async def test_grpc_bidi_streaming(monkeypatch, authed_client):
    name, ver = 'gbidi', 'v1'
    await _setup_api(authed_client, name, ver)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.importlib, 'import_module', _fake_import('gs'))

    class Chan:
        def stream_stream(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req_iter, metadata=None):
                class Msg:
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                    ok = True
                async for _ in req_iter:
                    yield Msg()
            return _call
    class _Aio:
        @staticmethod
        def insecure_channel(url): return Chan()
    monkeypatch.setattr(gs, 'grpc', type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}))

    body = {'method': 'Svc.M', 'message': {}, 'stream': 'bidi', 'messages': [{}, {}, {}], 'max_items': 2}
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json=body)
    assert r.status_code == 200
    data = r.json().get('response') or r.json()
    assert isinstance(data.get('items'), list) and len(data['items']) == 2


@pytest.mark.asyncio
async def test_grpc_bidi_streaming_field_echo(monkeypatch, authed_client):
    name, ver = 'gbidimap', 'v1'
    await _setup_api(authed_client, name, ver)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.importlib, 'import_module', _fake_import('gs'))

    class Chan:
        def stream_stream(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req_iter, metadata=None):
                class Msg:
                    def __init__(self, v):
                        self.val = v
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'val'})()]})()
                async for req in req_iter:
                    yield Msg(getattr(req, 'val', None))
            return _call
    class _Aio:
        @staticmethod
        def insecure_channel(url): return Chan()
    monkeypatch.setattr(gs, 'grpc', type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}))

    msgs = [{'val': 7}, {'val': 8}]
    body = {'method': 'Svc.M', 'message': {}, 'stream': 'bidi', 'messages': msgs, 'max_items': 10}
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json=body)
    assert r.status_code == 200
    data = r.json().get('response') or r.json()
    vals = [it.get('val') for it in (data.get('items') or [])]
    assert vals == [7, 8]
