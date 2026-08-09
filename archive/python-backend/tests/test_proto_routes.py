import io
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_proto_upload_and_get(monkeypatch, authed_client):
    import routes.proto_routes as pr

    class _FakeCompleted:
        pass

    def _fake_run(*args, **kwargs):
        command = args[0]
        for argument in command:
            if str(argument).startswith('--descriptor_set_out='):
                Path(str(argument).split('=', 1)[1]).write_bytes(b'descriptor')
        return _FakeCompleted()

    monkeypatch.setattr(pr.subprocess, 'run', _fake_run)

    proto_content = b"""
        syntax = "proto3";
        message Hello { string name = 1; }
    """
    files = {'file': ('hello.proto', io.BytesIO(proto_content), 'text/plain')}
    up = await authed_client.post('/platform/proto/myapi/v1', files=files)
    assert up.status_code in (200, 201)

    gp = await authed_client.get('/platform/proto/myapi/v1')
    assert gp.status_code == 200
    content = gp.json().get('content') or gp.json().get('response', {}).get('content')
    assert 'syntax = "proto3";' in content


@pytest.mark.asyncio
async def test_api_creation_attaches_a_proto_uploaded_first(monkeypatch, authed_client):
    import routes.proto_routes as pr
    from utils.async_db import db_find_one

    class _FakeCompleted:
        pass

    def _fake_run(*args, **kwargs):
        for argument in args[0]:
            if str(argument).startswith('--descriptor_set_out='):
                Path(str(argument).split('=', 1)[1]).write_bytes(b'preuploaded-descriptor')
        return _FakeCompleted()

    monkeypatch.setattr(pr.subprocess, 'run', _fake_run)
    api_name = 'proto-before-api'
    api_version = 'v1'
    proto_content = b'syntax = "proto3"; message Hello { string name = 1; }'

    try:
        upload = await authed_client.post(
            f'/platform/proto/{api_name}/{api_version}',
            files={'file': ('hello.proto', io.BytesIO(proto_content), 'text/plain')},
        )
        assert upload.status_code in (200, 201), upload.text

        created = await authed_client.post(
            '/platform/api',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'api_type': 'GRPC',
                'api_servers': ['grpc://127.0.0.1:50051'],
            },
        )
        assert created.status_code in (200, 201), created.text

        stored = await db_find_one(
            pr.api_collection, {'api_name': api_name, 'api_version': api_version}
        )
        assert stored['api_grpc_descriptor_set']
        assert stored['api_grpc_descriptor_sha256']
        assert stored['api_grpc_proto_source'] == proto_content.decode()
    finally:
        await authed_client.delete(f'/platform/proto/{api_name}/{api_version}')
        await authed_client.delete(f'/platform/api/{api_name}/{api_version}')


@pytest.mark.asyncio
async def test_descriptor_backfill_compiles_missing_active_grpc_api(monkeypatch, tmp_path):
    import routes.proto_routes as pr
    import utils.async_db as async_db

    async def _find(_collection, _query):
        return [
            {
                'api_name': 'orders',
                'api_version': 'v1',
                'api_type': 'grpc',
                'active': True,
                'api_grpc_proto_source': 'syntax = "proto3"; message Order {}',
            },
            {
                'api_name': 'ready',
                'api_version': 'v1',
                'api_type': 'grpc',
                'active': True,
                'api_grpc_descriptor_set': 'already-present',
            },
        ]

    persisted = []

    async def _persist(api_name, api_version, proto_root, compile_input, proto_content):
        persisted.append((api_name, api_version, proto_root, compile_input, proto_content))

    proto_path = tmp_path / 'orders_v1.proto'
    monkeypatch.setattr(async_db, 'db_find_list', _find)
    monkeypatch.setattr(pr, 'get_safe_proto_path', lambda *_args: (proto_path, tmp_path))
    monkeypatch.setattr(pr, 'persist_descriptor_set', _persist)

    result = await pr.backfill_descriptor_sets()

    assert result == {'scanned': 2, 'updated': 1, 'skipped': 1, 'missing': 0, 'errors': []}
    assert persisted[0][:2] == ('orders', 'v1')
    assert proto_path.read_text().startswith('syntax = "proto3"')
