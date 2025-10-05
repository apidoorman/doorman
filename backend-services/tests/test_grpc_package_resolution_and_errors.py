import pytest


async def _setup_api(client, name, ver, retry=0, api_pkg=None):
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
    if api_pkg is not None:
        payload['api_grpc_package'] = api_pkg
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
                # default: provide classes so gateway can proceed
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
            # service module with Stub class
            class Stub:
                def __init__(self, ch):
                    self._ch = ch
                async def M(self, req):
                    # Default success path
                    return type('R', (), {'DESCRIPTOR': type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})(), 'ok': True})()
            mod = type('SVC', (), {'SvcStub': Stub})
            return mod
        raise ImportError(name)
    return _imp


def _make_fake_grpc_unary(sequence_codes, grpc_mod):
    # Build a fake aio channel whose unary_unary returns a coroutine function using sequence codes
    counter = {'i': 0}
    class AioChan:
        async def channel_ready(self):
            return True
    class Chan(AioChan):
        def unary_unary(self, method, request_serializer=None, response_deserializer=None):
            async def _call(req):
                idx = min(counter['i'], len(sequence_codes) - 1)
                code = sequence_codes[idx]
                counter['i'] += 1
                if code is None:
                    # success
                    return type('R', (), {'DESCRIPTOR': type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})(), 'ok': True})()
                # Raise RpcError-like
                class E(Exception):
                    def code(self):
                        return code
                    def details(self):
                        return 'err'
                raise E()
            return _call
    class aio:
        @staticmethod
        def insecure_channel(url):
            return Chan()
    fake = type('G', (), {'aio': aio, 'StatusCode': grpc_mod.StatusCode, 'RpcError': Exception})
    return fake


@pytest.mark.asyncio
async def test_grpc_uses_api_grpc_package_over_request(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gpack1', 'v1'
    await _setup_api(authed_client, name, ver, api_pkg='api.pkg')
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    pb2_map = { 'api.pkg_pb2': (req_cls, rep_cls) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    # Skip on-demand proto generation/import checks
    monkeypatch.setattr(gs.os.path, 'exists', lambda p: True)
    # Fake grpc to always succeed
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}, 'package': 'req.pkg'}
    )
    assert r.status_code == 200
    assert any(n == 'api.pkg_pb2' for n in record)


@pytest.mark.asyncio
async def test_grpc_uses_request_package_when_no_api_package(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gpack2', 'v1'
    await _setup_api(authed_client, name, ver, api_pkg=None)
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    pb2_map = { 'req.pkg_pb2': (req_cls, rep_cls) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    monkeypatch.setattr(gs.os.path, 'exists', lambda p: True)
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}, 'package': 'req.pkg'}
    )
    assert r.status_code == 200
    assert any(n == 'req.pkg_pb2' for n in record)


@pytest.mark.asyncio
async def test_grpc_uses_default_package_when_no_overrides(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gpack3', 'v1'
    await _setup_api(authed_client, name, ver, api_pkg=None)
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    pb2_map = { default_pkg: (req_cls, rep_cls) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    monkeypatch.setattr(gs.os.path, 'exists', lambda p: True)
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 200
    assert any(n.endswith(default_pkg) for n in record)


@pytest.mark.asyncio
async def test_grpc_unavailable_then_success_with_retry(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gunavail', 'v1'
    await _setup_api(authed_client, name, ver, retry=1)
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    pb2_map = { default_pkg: (req_cls, rep_cls) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    # First UNAVAILABLE, then success
    fake_grpc = _make_fake_grpc_unary([gs.grpc.StatusCode.UNAVAILABLE, None], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake_grpc)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_grpc_unimplemented_then_success_with_retry(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gunimpl', 'v1'
    await _setup_api(authed_client, name, ver, retry=1)
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    pb2_map = { default_pkg: (req_cls, rep_cls) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    fake_grpc = _make_fake_grpc_unary([gs.grpc.StatusCode.UNIMPLEMENTED, None], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake_grpc)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_grpc_not_found_maps_to_500_error(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gnotfound', 'v1'
    await _setup_api(authed_client, name, ver)
    # Cause missing method types -> AttributeError -> GTW006 500
    record = []
    # Provide pb2 without classes to force failure
    pb2_map = { f'{name}_{ver}_pb2': (None, None) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 500
    body = r.json()
    assert body.get('error_code') == 'GTW006'


@pytest.mark.asyncio
async def test_grpc_unknown_maps_to_500_error(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gunk', 'v1'
    await _setup_api(authed_client, name, ver)
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    pb2_map = { default_pkg: (req_cls, rep_cls) }
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    # Force UNKNOWN error (maps to 500)
    fake_grpc = _make_fake_grpc_unary([gs.grpc.StatusCode.UNKNOWN], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake_grpc)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 500


@pytest.mark.asyncio
async def test_grpc_proto_missing_returns_404_gtw012(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gproto404', 'v1'
    await _setup_api(authed_client, name, ver)
    # Make on-demand proto generation fail by raising on import grpc_tools
    def _imp_fail(name):
        if name.startswith('grpc_tools'):
            raise ImportError('no tools')
        raise ImportError(name)
    monkeypatch.setattr(gs.importlib, 'import_module', _imp_fail)
    r = await authed_client.post(
        f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}}
    )
    assert r.status_code == 404
    body = r.json()
    assert body.get('error_code') == 'GTW012'
