import pytest
from servers import start_graphql_json_server


def test_graphql_public_local_via_gateway(client):
    """Exercise a public GraphQL API through the gateway using a local helper server."""
    api_name = 'gqlpub'
    api_version = 'v1'

    srv = start_graphql_json_server({'data': {'characters': {'info': {'count': 123}}}})

    r = client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'Public GraphQL (local)',
            'api_allowed_roles': [],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_public': True,
            'api_auth_required': False,
        },
    )
    assert r.status_code in (200, 201), r.text

    r = client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'POST',
            'endpoint_uri': '/graphql',
            'endpoint_description': 'GraphQL endpoint',
        },
    )
    assert r.status_code in (200, 201), r.text

    q = '{ characters(page: 1) { info { count } } }'
    r = client.post(
        f'/api/graphql/{api_name}',
        json={'query': q, 'variables': {}},
        headers={'X-API-Version': api_version, 'Content-Type': 'application/json'},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    data = body.get('response', body).get('data') if isinstance(body, dict) else None
    if data is None and 'data' in body:
        data = body.get('data')
    assert isinstance(data, dict) and 'characters' in data
