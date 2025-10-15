import pytest

async def _setup_api(client, name, ver, retry=0):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:50051'],
        'api_type': 'REST',
        'api_allowed_retry_count': retry,
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

def _fake_pb2_module(method_name='M'):
    class Req:
        pass
    class Reply:
        DESCRIPTOR = type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})()
        def __init__(self, ok=True):
            self.ok = ok
        @staticmethod
        def FromString(b):
            return Reply(True)
    setattr(Req, '__name__', f'{method_name}Request')
    setattr(Reply, '__name__', f'{method_name}Reply')
    return Req, Reply

def _make_import_module_recorder(record, pb2_map):
    def _imp(name):
        record.append(name)
        if name.endswith('_pb2'):
            mod = type('PB2', (), {})
            mapping = pb2_map.get(name)
            if mapping is None:
                req_cls, rep_cls = _fake_pb2_module('M')
                setattr(mod, 'MRequest', req_cls)
                setattr(mod, 'MReply', rep_cls)
            else:
                req_cls, rep_cls = mapping
                if req_cls:
                    setattr(mod, 'MRequest', req_cls)
                if rep_cls:
                    setattr(mod, 'MReply', rep_cls)
            return mod
        if name.endswith('_pb2_grpc'):
            class Stub:
                def __init__(self, ch):
                    self._ch = ch
                async def M(self, req):
                    return type('R', (), {'DESCRIPTOR': type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})(), 'ok': True})()
            return type('SVC', (), {'SvcStub': Stub})
        raise ImportError(name)
    return _imp

def _make_fake_grpc_unary(sequence_codes, grpc_mod):
    counter = {'i': 0}
    class Chan:
        def unary_unary(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req, metadata=None):
                idx = min(counter['i'], len(sequence_codes) - 1)
                code = sequence_codes[idx]
                counter['i'] += 1
                if code is None:
                    return type('R', (), {'DESCRIPTOR': type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})(), 'ok': True})()
                class E(grpc_mod.RpcError):
                    def code(self):
                        return code
                    def details(self):
                        return f'{code.name}'
                raise E()
            return _call
    class aio:
        @staticmethod
        def insecure_channel(url):
            return Chan()
    return type('G', (), {'aio': aio, 'StatusCode': grpc_mod.StatusCode, 'RpcError': Exception})

@pytest.mark.asyncio
async def test_grpc_status_mappings_basic(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gmap', 'v1'
    await _setup_api(authed_client, name, ver, retry=0)
    rec = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(rec, {default_pkg: (req_cls, rep_cls)}))

    cases = [
        (gs.grpc.StatusCode.UNAUTHENTICATED, 401),
        (gs.grpc.StatusCode.PERMISSION_DENIED, 403),
        (gs.grpc.StatusCode.NOT_FOUND, 404),
        (gs.grpc.StatusCode.RESOURCE_EXHAUSTED, 429),
        (gs.grpc.StatusCode.UNIMPLEMENTED, 501),
        (gs.grpc.StatusCode.UNAVAILABLE, 503),
    ]
    for code, expect in cases:
        fake = _make_fake_grpc_unary([code], gs.grpc)
        monkeypatch.setattr(gs, 'grpc', fake)
        r = await authed_client.post(
            f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
        )
        assert r.status_code == expect

@pytest.mark.asyncio
async def test_grpc_unavailable_with_retry_still_fails_maps_503(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gunav', 'v1'
    await _setup_api(authed_client, name, ver, retry=2)
    rec = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(rec, {default_pkg: (req_cls, rep_cls)}))
    fake = _make_fake_grpc_unary([gs.grpc.StatusCode.UNAVAILABLE, gs.grpc.StatusCode.UNAVAILABLE, gs.grpc.StatusCode.UNAVAILABLE], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 503

@pytest.mark.asyncio
async def test_grpc_alt_method_fallback_succeeds(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'galt', 'v1'
    await _setup_api(authed_client, name, ver, retry=0)

    rec = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(rec, {default_pkg: (req_cls, rep_cls)}))
    fake = _make_fake_grpc_unary([gs.grpc.StatusCode.ABORTED, None], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_grpc_non_retryable_error_returns_500_no_retry(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gnr', 'v1'
    await _setup_api(authed_client, name, ver, retry=2)
    rec = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(rec, {default_pkg: (req_cls, rep_cls)}))
    fake = _make_fake_grpc_unary([gs.grpc.StatusCode.INVALID_ARGUMENT, gs.grpc.StatusCode.INVALID_ARGUMENT], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 400
    assert r.json().get('error_code') == 'GTW006'

@pytest.mark.asyncio
async def test_grpc_deadline_exceeded_maps_to_504(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gdl', 'v1'
    await _setup_api(authed_client, name, ver, retry=1)
    rec = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(rec, {default_pkg: (req_cls, rep_cls)}))
    fake = _make_fake_grpc_unary([gs.grpc.StatusCode.DEADLINE_EXCEEDED], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 504
    assert r.json().get('error_code') == 'GTW006'

@pytest.mark.asyncio
async def test_grpc_unavailable_then_unimplemented_then_success(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gretry', 'v1'
    await _setup_api(authed_client, name, ver, retry=3)
    rec = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(rec, {default_pkg: (req_cls, rep_cls)}))
    fake = _make_fake_grpc_unary([gs.grpc.StatusCode.UNAVAILABLE, gs.grpc.StatusCode.UNIMPLEMENTED, None], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 200
