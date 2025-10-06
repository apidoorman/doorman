import os
import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')


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
            mod = type('SVC', (), {'SvcStub': Stub})
            return mod
        raise ImportError(name)
    return _imp


def _make_fake_grpc_unary(sequence_codes, grpc_mod):
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
                    return type('R', (), {'DESCRIPTOR': type('D', (), {'fields': [type('F', (), {'name': 'ok'})()]})(), 'ok': True})()
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
async def test_grpc_with_api_grpc_package_config(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gplive1', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': 'g',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:9'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_grpc_package': 'api.pkg'
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/grpc',
        'endpoint_description': 'grpc'
    })
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    pb2_map = {'api.pkg_pb2': (req_cls, rep_cls)}
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    monkeypatch.setattr(gs.os.path, 'exists', lambda p: True)
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}, 'package': 'req.pkg'})
    assert r.status_code == 200
    assert any(n == 'api.pkg_pb2' for n in record)


@pytest.mark.asyncio
async def test_grpc_with_request_package_override(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gplive2', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': 'g',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:9'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/grpc',
        'endpoint_description': 'grpc'
    })
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    pb2_map = {'req.pkg_pb2': (req_cls, rep_cls)}
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    monkeypatch.setattr(gs.os.path, 'exists', lambda p: True)
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}, 'package': 'req.pkg'})
    assert r.status_code == 200
    assert any(n == 'req.pkg_pb2' for n in record)


@pytest.mark.asyncio
async def test_grpc_without_package_server_uses_fallback_path(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gplive3', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': 'g',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:9'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/grpc',
        'endpoint_description': 'grpc'
    })
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    pb2_map = {default_pkg: (req_cls, rep_cls)}
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    monkeypatch.setattr(gs.os.path, 'exists', lambda p: True)
    monkeypatch.setattr(gs, 'grpc', _make_fake_grpc_unary([None], gs.grpc))
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}})
    assert r.status_code == 200
    assert any(n.endswith(default_pkg) for n in record)


@pytest.mark.asyncio
async def test_grpc_unavailable_then_success_with_retry_live(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'gplive4', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': 'g',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:9'],
        'api_type': 'REST',
        'api_allowed_retry_count': 1,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/grpc',
        'endpoint_description': 'grpc'
    })
    record = []
    req_cls, rep_cls = _fake_pb2_module('M')
    default_pkg = f'{name}_{ver}'.replace('-', '_') + '_pb2'
    pb2_map = {default_pkg: (req_cls, rep_cls)}
    monkeypatch.setattr(gs.importlib, 'import_module', _make_import_module_recorder(record, pb2_map))
    fake_grpc = _make_fake_grpc_unary([gs.grpc.StatusCode.UNAVAILABLE, None], gs.grpc)
    monkeypatch.setattr(gs, 'grpc', fake_grpc)
    r = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}})
    assert r.status_code == 200
