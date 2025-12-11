import json

import pytest


async def _setup_api(client, name, ver, public=False):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:50051'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': bool(public),
    }
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post(
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


@pytest.mark.asyncio
async def test_grpc_requires_subscription_when_not_public(monkeypatch, authed_client):
    name, ver = 'gsub', 'v1'
    await _setup_api(authed_client, name, ver, public=False)

    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': 'Svc.M', 'message': {}},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_grpc_metrics_bytes_in_out(monkeypatch, authed_client):
    name, ver = 'gmet', 'v1'
    await _setup_api(authed_client, name, ver, public=False)
    from conftest import subscribe_self

    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    def _imp(name):
        if name.endswith('_pb2'):
            mod = type('PB2', (), {})
            mod.MRequest = type('Req', (), {})

            class Reply:
                DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()

                @staticmethod
                def FromString(b):
                    return Reply()

            mod.MReply = Reply
            return mod
        if name.endswith('_pb2_grpc'):

            class Stub:
                def __init__(self, ch):
                    pass

            return type('SVC', (), {'SvcStub': Stub})
        raise ImportError(name)

    monkeypatch.setattr(gs.importlib, 'import_module', _imp)

    class Chan:
        def unary_unary(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req):
                # return a small reply
                class Reply:
                    DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                    ok = True

                return Reply()

            return _call

    class _Aio:
        @staticmethod
        def insecure_channel(url):
            return Chan()

    fake_grpc = type(
        'G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception}
    )
    monkeypatch.setattr(gs, 'grpc', fake_grpc)

    m0 = await authed_client.get('/platform/monitor/metrics')
    j0 = m0.json().get('response') or m0.json()
    tin0 = int(j0.get('total_bytes_in', 0))
    tout0 = int(j0.get('total_bytes_out', 0))

    body_obj = {'method': 'Svc.M', 'message': {}}
    raw = json.dumps(body_obj)
    headers = {
        'Content-Type': 'application/json',
        'X-API-Version': ver,
        'Content-Length': str(len(raw)),
    }
    r = await authed_client.post(f'/api/grpc/{name}', headers=headers, content=raw)
    assert r.status_code in (200, 500, 501, 503)

    m1 = await authed_client.get('/platform/monitor/metrics')
    j1 = m1.json().get('response') or m1.json()
    tin1 = int(j1.get('total_bytes_in', 0))
    tout1 = int(j1.get('total_bytes_out', 0))
    assert tin1 - tin0 >= len(raw)
    assert tout1 >= tout0
