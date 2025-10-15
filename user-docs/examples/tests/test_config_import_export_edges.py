import pytest

@pytest.mark.asyncio
async def test_import_invalid_payload_returns_error(authed_client):
    r = await authed_client.post('/platform/config/import', json=[{"not": "a dict"}])
    assert r.status_code == 422, r.text
    j = r.json()
    assert (j.get('error_code') or j.get('response', {}).get('error_code')) in ('VAL001', 'GTW999')

@pytest.mark.asyncio
async def test_export_includes_expected_sections(authed_client):
    r = await authed_client.get('/platform/config/export/all')
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    for key in ('apis', 'endpoints', 'roles', 'groups', 'routings'):
        assert key in payload, f"missing section: {key}"
        assert isinstance(payload[key], list)

@pytest.mark.asyncio
async def test_import_export_roundtrip_idempotent(authed_client):
    r1 = await authed_client.get('/platform/config/export/all')
    assert r1.status_code == 200
    export_blob = r1.json().get('response', r1.json())

    r2 = await authed_client.post('/platform/config/import', json=export_blob)
    assert r2.status_code == 200
    imported = r2.json().get('response', r2.json())
    assert 'imported' in imported

    r3 = await authed_client.get('/platform/config/export/all')
    assert r3.status_code == 200
    export_after = r3.json().get('response', r3.json())

    def _counts(blob):
        return {k: len(blob.get(k, [])) for k in ('apis', 'endpoints', 'roles', 'groups', 'routings')}

    assert _counts(export_after) == _counts(export_blob)

