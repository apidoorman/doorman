import pytest
from live_targets import GRAPHQL_TARGETS


def test_graphql_public_local_via_gateway(client):
    """Exercise a public GraphQL API through the gateway using a live upstream."""
    api_name = 'gqlpub'
    api_version = 'v1'

    server_url, query = GRAPHQL_TARGETS[0]

    r = client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'Public GraphQL (live)',
            'api_allowed_roles': [],
            'api_allowed_groups': ['ALL'],
            'api_servers': [server_url],
            'api_type': 'GRAPHQL',
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

    q = query
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
    assert isinstance(data, dict)
