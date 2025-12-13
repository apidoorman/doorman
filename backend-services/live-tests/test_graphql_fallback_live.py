import pytest

from servers import start_graphql_json_server


async def _setup(client, upstream_url: str, name='gllive', ver='v1'):
    await client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [upstream_url],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_public': True,
        },
    )
    await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/graphql',
            'endpoint_description': 'gql',
        },
    )
    return name, ver


@pytest.mark.asyncio
async def test_graphql_json_proxy_ok(authed_client):
    # Upstream returns a fixed JSON body
    srv = start_graphql_json_server({'ok': True})
    try:
        name, ver = await _setup(authed_client, upstream_url=srv.url, name='gll1')
        r = await authed_client.post(
            f'/api/graphql/{name}',
            headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
            json={'query': '{ ping }', 'variables': {}},
        )
        assert r.status_code == 200 and r.json().get('ok') is True
    finally:
        srv.stop()


@pytest.mark.asyncio
async def test_graphql_errors_array_passthrough(authed_client):
    # Upstream returns a GraphQL-style errors array
    srv = start_graphql_json_server({'errors': [{'message': 'boom'}]})
    try:
        name, ver = await _setup(authed_client, upstream_url=srv.url, name='gll2')
        r1 = await authed_client.post(
            f'/api/graphql/{name}',
            headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
            json={'query': '{ err }', 'variables': {}},
        )
        assert r1.status_code == 200 and isinstance(r1.json().get('errors'), list)
    finally:
        srv.stop()
