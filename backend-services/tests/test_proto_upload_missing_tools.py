import io
import sys
import types

import pytest


@pytest.mark.asyncio
async def test_proto_upload_fails_with_clear_message_when_tools_missing(monkeypatch, authed_client):
    # Ensure grpc_tools is not importable
    for mod in list(sys.modules.keys()):
        if mod.startswith('grpc_tools'):
            del sys.modules[mod]
    # Also block import by setting a placeholder package that raises
    def _fail_import(name, *a, **k):
        if name.startswith('grpc_tools'):
            raise ImportError('No module named grpc_tools')
        return orig_import(name, *a, **k)

    orig_import = __import__
    monkeypatch.setattr('builtins.__import__', _fail_import)

    api_name, api_version = 'xproto', 'v1'
    # Create admin API to satisfy auth; not strictly required for /proto
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'gRPC test',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['grpc://localhost:9'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )

    proto_content = b"syntax = \"proto3\"; package xproto_v1; service S { rpc M (A) returns (B) {} } message A { string n = 1; } message B { string m = 1; }"
    files = {'proto_file': ('svc.proto', proto_content, 'application/octet-stream')}
    r = await authed_client.post(f'/platform/proto/{api_name}/{api_version}', files=files)
    # Expect clear message about missing tools
    assert r.status_code == 500
    body = r.json().get('response', r.json())
    msg = body.get('error_message') or ''
    assert 'grpcio-tools' in msg or 'gRPC tools not available' in msg
