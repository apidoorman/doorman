import pytest


@pytest.mark.asyncio
async def test_api_get_by_name_version_returns_200(authed_client):
    name, ver = 'apiget', 'v1'
    r = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'demo',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://upstream.invalid'],
            'api_type': 'REST',
            'active': True,
        },
    )
    assert r.status_code in (200, 201), r.text

    g = await authed_client.get(f'/platform/api/{name}/{ver}')
    assert g.status_code == 200, g.text
    body = g.json().get('response', g.json())
    assert body.get('api_name') == name
    assert body.get('api_version') == ver
    assert '_id' not in body
