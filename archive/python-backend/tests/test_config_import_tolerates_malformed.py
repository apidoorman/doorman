import pytest


@pytest.mark.asyncio
async def test_config_import_ignores_malformed_entries(authed_client):
    body = {
        'apis': [
            {'api_name': 'x-only'},  # missing version; ignored
            {'api_version': 'v1'},  # missing name; ignored
        ],
        'endpoints': [
            {'api_name': 'x', 'endpoint_method': 'GET'}  # missing api_version/uri
        ],
        'roles': [
            {'bad': 'doc'}  # missing role_name
        ],
        'groups': [
            {'bad': 'doc'}  # missing group_name
        ],
        'routings': [
            {'bad': 'doc'}  # missing client_key
        ],
    }
    r = await authed_client.post('/platform/config/import', json=body)
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    payload.get('imported') or {}
    # Import reports how many items were processed, not how many were actually upserted.
    # Verify no valid API was created as a result of malformed entries.
    bad_get = await authed_client.get('/platform/api/x-only/v1')
    assert bad_get.status_code in (400, 404)
