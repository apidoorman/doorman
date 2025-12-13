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
    
    # Mock importlib.import_module to simulate grpc_tools.protoc missing
    import importlib
    original_import = importlib.import_module
    
    def mock_import(name, *args, **kwargs):
        if name == 'grpc_tools.protoc':
            raise ModuleNotFoundError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr('importlib.import_module', mock_import)

    r = await authed_client.get('/platform/tools/grpc/check')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    assert body['available']['grpc'] is True
    assert body['available']['grpc_tools_protoc'] is False
    assert any('grpcio-tools' in n for n in (body.get('notes') or []))
