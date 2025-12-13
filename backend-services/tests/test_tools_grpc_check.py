import types

import pytest


async def _allow_tools(client):
    await client.put('/platform/user/admin', json={'manage_security': True})


@pytest.mark.asyncio
async def test_grpc_check_reports_all_present(monkeypatch, authed_client):
    await _allow_tools(authed_client)
    # Fake modules for grpc and grpc_tools.protoc
    fake_grpc = types.ModuleType('grpc')
    fake_tools = types.ModuleType('grpc_tools')
    fake_protoc = types.ModuleType('grpc_tools.protoc')
    fake_tools.protoc = fake_protoc  # type: ignore[attr-defined]

    import sys

    sys.modules['grpc'] = fake_grpc
    sys.modules['grpc_tools'] = fake_tools
    sys.modules['grpc_tools.protoc'] = fake_protoc

    r = await authed_client.get('/platform/tools/grpc/check')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    assert body['available']['grpc'] is True
    assert body['available']['grpc_tools_protoc'] is True
    assert isinstance(body.get('notes'), list)


@pytest.mark.asyncio
async def test_grpc_check_reports_missing_protoc(monkeypatch, authed_client):
    await _allow_tools(authed_client)
    # Ensure grpc present, but grpc_tools.protoc missing
    import sys
    fake_grpc = types.ModuleType('grpc')
    sys.modules['grpc'] = fake_grpc
    for mod in list(sys.modules.keys()):
        if mod.startswith('grpc_tools'):
            del sys.modules[mod]

    r = await authed_client.get('/platform/tools/grpc/check')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    assert body['available']['grpc'] is True
    assert body['available']['grpc_tools_protoc'] is False
    assert any('grpcio-tools' in n for n in (body.get('notes') or []))
