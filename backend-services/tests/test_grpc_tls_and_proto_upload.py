import os
import sys
from pathlib import Path

import pytest


async def _create_api(client, name: str, ver: str, server_url: str):
    r = await client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_servers': [server_url],
            'api_type': 'REST',
            'api_public': True,
            'api_allowed_retry_count': 0,
            'active': True,
            'api_grpc_package': 'svc',
        },
    )
    assert r.status_code in (200, 201), r.text
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
    assert r2.status_code in (200, 201), r2.text


@pytest.mark.asyncio
async def test_grpc_selects_secure_channel(monkeypatch, authed_client):
    name, ver = 'grpc_tls', 'v1'
    # Create an API pointing at a TLS endpoint (host doesn't need to exist since we monkeypatch)
    await _create_api(authed_client, name, ver, 'grpcs://example.test:443')

    import services.gateway_service as gs

    called = {'secure': 0, 'insecure': 0}

    class _Chan:
        def unary_unary(self, *a, **k):  # minimal surface
            async def _call(*_a, **_k):
                class R:
                    DESCRIPTOR = type('D', (), {'fields': []})()

                return R()

            return _call

    class _Aio:
        @staticmethod
        def secure_channel(target, creds):
            called['secure'] += 1
            return _Chan()

        @staticmethod
        def insecure_channel(target):
            called['insecure'] += 1
            return _Chan()

    # Provide minimal pb2 module so gateway can build request/response without reflection
    pb2 = type('PB2', (), {})
    setattr(pb2, 'DESCRIPTOR', type('DESC', (), {'services_by_name': {}})())
    # Force import_module to return our pb2/pb2_grpc for svc package
    def _fake_import(name):
        if name.endswith('_pb2'):
            # Provide fallback Request/Reply class names used by the gateway when descriptors are absent
            class MRequest:
                pass

            class MReply:
                @staticmethod
                def FromString(b):
                    return MReply()

            setattr(pb2, 'MRequest', MRequest)
            setattr(pb2, 'MReply', MReply)
            return pb2
        if name.endswith('_pb2_grpc'):
            return type('S', (), {})
        raise ImportError(name)

    monkeypatch.setattr(gs.importlib, 'import_module', _fake_import)
    monkeypatch.setattr(gs.grpc, 'aio', _Aio)

    body = {'method': 'M.M', 'message': {}}
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json=body,
    )
    assert r.status_code in (200, 500)  # response path not important here
    # Ensure we attempted secure channel
    assert called['secure'] >= 1
    # And did not fall back to insecure unless TLS creds failed
    assert called['insecure'] in (0, 1)


@pytest.mark.asyncio
async def test_proto_upload_preserves_package_and_generates_under_package(authed_client):
    name, ver = 'pkgpres', 'v1'
    proto = (
        'syntax = "proto3";\n'
        'package my.pkg;\n'
        'message HelloRequest { string name = 1; }\n'
        'message HelloReply { string message = 1; }\n'
        'service Svc { rpc M (HelloRequest) returns (HelloReply); }\n'
    )
    files = {'file': ('svc.proto', proto.encode('utf-8'), 'application/octet-stream')}
    r = await authed_client.post(f'/platform/proto/{name}/{ver}', files=files)
    assert r.status_code == 200, r.text

    # The original proto should be retrievable and preserve the package line
    g = await authed_client.get(f'/platform/proto/{name}/{ver}')
    assert g.status_code == 200
    data = g.json()
    content = (data.get('response', {}) or {}).get('content') if 'response' in data else data.get('content')
    content = content or ''
    assert 'package my.pkg;' in content

    # Generated modules should exist under routes/generated/my/pkg*_pb2*.py
    base = Path(__file__).resolve().parent.parent / 'routes'
    gen = (base / 'generated').resolve()
    pb2 = gen / 'my' / 'pkg_pb2.py'
    pb2grpc = gen / 'my' / 'pkg_pb2_grpc.py'
    assert pb2.is_file(), f'missing {pb2}'
    assert pb2grpc.is_file(), f'missing {pb2grpc}'
