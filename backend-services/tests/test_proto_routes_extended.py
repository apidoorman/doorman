import pytest


@pytest.mark.asyncio
async def test_proto_update_and_delete_flow(monkeypatch, authed_client):
    import routes.proto_routes as pr

    class _FakeCompleted:
        pass

    def _fake_run(*args, **kwargs):
        return _FakeCompleted()

    monkeypatch.setattr(pr.subprocess, 'run', _fake_run)

    r = await authed_client.put('/platform/role/admin', json={'manage_apis': True})
    assert r.status_code in (200, 201)

    files = {
        'file': ('sample.proto', b'syntax = "proto3"; message Ping { string x = 1; }', 'text/plain')
    }
    up = await authed_client.post('/platform/proto/myapi2/v1', files=files)
    assert up.status_code in (200, 201), up.text

    files2 = {
        'proto_file': (
            'sample.proto',
            b'syntax = "proto3"; message Pong { string y = 1; }',
            'text/plain',
        )
    }
    put = await authed_client.put('/platform/proto/myapi2/v1', files=files2)
    assert put.status_code in (200, 201), put.text

    gp = await authed_client.get('/platform/proto/myapi2/v1')
    assert gp.status_code == 200
    body = gp.json()
    content = body.get('response', {}).get('content') or body.get('content', '')
    assert 'Pong' in content or 'message Pong' in content

    dl = await authed_client.delete('/platform/proto/myapi2/v1')
    assert dl.status_code in (200, 204)

    gp2 = await authed_client.get('/platform/proto/myapi2/v1')
    assert gp2.status_code == 404


@pytest.mark.asyncio
async def test_proto_get_nonexistent_returns_404(authed_client):
    resp = await authed_client.get('/platform/proto/doesnotexist/v9')
    assert resp.status_code == 404
