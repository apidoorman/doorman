import pytest

@pytest.mark.asyncio
async def test_logging_requires_permissions(authed_client):

    r = await authed_client.put(
        '/platform/role/admin',
        json={'view_logs': False, 'export_logs': False},
    )
    assert r.status_code in (200, 201)

    logs = await authed_client.get('/platform/logging/logs?limit=5')
    assert logs.status_code == 403

    files = await authed_client.get('/platform/logging/logs/files')
    assert files.status_code == 403

    stats = await authed_client.get('/platform/logging/logs/statistics')
    assert stats.status_code == 403

    export = await authed_client.get('/platform/logging/logs/export?format=json')
    assert export.status_code == 403

    download = await authed_client.get('/platform/logging/logs/download?format=csv')
    assert download.status_code == 403

    r2 = await authed_client.put(
        '/platform/role/admin',
        json={'view_logs': True, 'export_logs': True},
    )
    assert r2.status_code in (200, 201)

    logs2 = await authed_client.get('/platform/logging/logs?limit=1')
    assert logs2.status_code == 200
    files2 = await authed_client.get('/platform/logging/logs/files')
    assert files2.status_code == 200
    export2 = await authed_client.get('/platform/logging/logs/download?format=json')
    assert export2.status_code == 200

