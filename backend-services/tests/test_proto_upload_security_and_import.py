import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_proto_upload_rejects_invalid_filename(monkeypatch, authed_client):
    # Force sanitize_filename to raise to simulate invalid input
    import routes.proto_routes as pr
    monkeypatch.setattr(pr, 'sanitize_filename', lambda s: (_ for _ in ()).throw(ValueError('bad')))
    files = {'file': ('svc.proto', b'syntax = "proto3"; package x;')}
    r = await authed_client.post('/platform/proto/bad/v1', files=files)
    assert r.status_code == 400
    body = r.json()
    assert body.get('error_code')


@pytest.mark.asyncio
async def test_proto_upload_validates_within_base_path():
    # Unit-test validate_path
    import routes.proto_routes as pr
    base = (pr.PROJECT_ROOT / 'proto').resolve()
    good = (base / 'ok.proto').resolve()
    bad = (pr.PROJECT_ROOT.parent / 'outside.proto').resolve()
    assert pr.validate_path(pr.PROJECT_ROOT, good) is True
    assert pr.validate_path(pr.PROJECT_ROOT, bad) is False


@pytest.mark.asyncio
async def test_proto_upload_generates_stubs_success(monkeypatch, authed_client):
    name, ver = 'psvc1', 'v1'
    proto = b'syntax = "proto3"; package foo; service S { rpc M (R) returns (Q) {} } message R { string a = 1; } message Q { string b = 1; }'
    files = {'file': ('svc.proto', proto)}
    import routes.proto_routes as pr
    safe = f'{name}_{ver}'
    gen = (pr.PROJECT_ROOT / 'generated').resolve()
    def _fake_run(cmd, check):
        # Simulate protoc output files
        (gen / f'{safe}_pb2.py').write_text('# pb2')
        (gen / f'{safe}_pb2_grpc.py').write_text(
            f'import {safe}_pb2 as {name}__{ver}__pb2\n'
            'class S: pass\n'
        )
        return 0
    monkeypatch.setattr(pr.subprocess, 'run', _fake_run)
    r = await authed_client.post(f'/platform/proto/{name}/{ver}', files=files)
    assert r.status_code == 200
    import routes.proto_routes as pr
    safe = f'{name}_{ver}'
    gen = (pr.PROJECT_ROOT / 'generated').resolve()
    assert (gen / f'{safe}_pb2.py').exists()
    assert (gen / f'{safe}_pb2_grpc.py').exists()


@pytest.mark.asyncio
async def test_proto_upload_rewrite_pb2_imports_for_generated_namespace(monkeypatch, authed_client):
    name, ver = 'psvc2', 'v1'
    proto = b'syntax = "proto3"; package foo; service S { rpc M (R) returns (Q) {} } message R { string a = 1; } message Q { string b = 1; }'
    files = {'file': ('svc.proto', proto)}
    import routes.proto_routes as pr
    safe = f'{name}_{ver}'
    gen = (pr.PROJECT_ROOT / 'generated').resolve()
    def _fake_run(cmd, check):
        (gen / f'{safe}_pb2.py').write_text('# pb2')
        (gen / f'{safe}_pb2_grpc.py').write_text(
            f'import {safe}_pb2 as {name}__{ver}__pb2\n'
            'class S: pass\n'
        )
        return 0
    monkeypatch.setattr(pr.subprocess, 'run', _fake_run)
    r = await authed_client.post(f'/platform/proto/{name}/{ver}', files=files)
    assert r.status_code == 200
    import routes.proto_routes as pr
    safe = f'{name}_{ver}'
    gen = (pr.PROJECT_ROOT / 'generated').resolve()
    pb2g = (gen / f'{safe}_pb2_grpc.py')
    txt = pb2g.read_text()
    # Ensure import was rewritten to from generated import <key>_pb2 ...
    assert f'from generated import {safe}_pb2 as {name}__{ver}__pb2' in txt


@pytest.mark.asyncio
async def test_proto_get_requires_permission(monkeypatch, authed_client):
    import routes.proto_routes as pr
    # Force permission check to fail
    async def _no_perm(*args, **kwargs):
        return False
    monkeypatch.setattr(pr, 'platform_role_required_bool', _no_perm)
    r = await authed_client.get('/platform/proto/x/v1')
    assert r.status_code == 403
    body = r.json()
    assert body.get('error_code')
