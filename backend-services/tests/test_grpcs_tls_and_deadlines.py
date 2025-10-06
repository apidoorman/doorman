import pytest


async def _setup_api(client, name, ver, url):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': [url],
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


@pytest.mark.asyncio
async def test_grpcs_misconfig_returns_500(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gtls', 'v1'
    await _setup_api(authed_client, name, ver, url='grpcs://example:50051')

    # Fake import pb2
    def _imp(name):
        if name.endswith('_pb2'):
            mod = type('PB2', (), {})
            setattr(mod, 'MRequest', type('Req', (), {}) )
            class Reply:
                DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
                @staticmethod
                def FromString(b):
                    return Reply()
            setattr(mod, 'MReply', Reply)
            return mod
        if name.endswith('_pb2_grpc'):
            class Stub:
                def __init__(self, ch): pass
            return type('SVC', (), {'SvcStub': Stub})
        raise ImportError(name)
    monkeypatch.setattr(gs.importlib, 'import_module', _imp)

    # Simulate insecure_channel rejecting grpcs:// URL
    class _Aio:
        @staticmethod
        def insecure_channel(url):
            if str(url).startswith('grpcs://'):
                raise RuntimeError('TLS required')
            return object()
    fake_grpc = type('G', (), {'aio': _Aio, 'StatusCode': gs.grpc.StatusCode, 'RpcError': Exception})
    monkeypatch.setattr(gs, 'grpc', fake_grpc)

    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code in (500, 501, 503)

