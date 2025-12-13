import os as _os

import pytest

_RUN_LIVE = _os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
_RUN_EXTERNAL = _os.getenv('DOORMAN_TEST_EXTERNAL', '0') in ('1', 'true', 'True')

pytestmark = pytest.mark.skipif(
    not (_RUN_LIVE and _RUN_EXTERNAL),
    reason='Requires external network; set DOORMAN_TEST_EXTERNAL=1 and DOORMAN_RUN_LIVE=1',
)


def test_graphql_public_rick_and_morty_via_gateway(client):
    """Exercise a real public GraphQL API through the gateway.

    Uses Rick & Morty GraphQL at https://rickandmortyapi.com/graphql
    """
    api_name = 'gqlpub'
    api_version = 'v1'

    # Create a public API that requires no auth
    r = client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'Public GraphQL (Rick & Morty)',
            'api_allowed_roles': [],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['https://rickandmortyapi.com'],
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

    # Query characters count (stable field)
    query = '{ characters(page: 1) { info { count } } }'
    r = client.post(
        f'/api/graphql/{api_name}',
        json={'query': query, 'variables': {}},
        headers={'X-API-Version': api_version, 'Content-Type': 'application/json'},
    )
    # Expect success with data
    assert r.status_code == 200, r.text
    body = r.json()
    # Accept either enveloped or raw data
    data = body.get('response', body).get('data') if isinstance(body, dict) else None
    if data is None and 'data' in body:
        data = body.get('data')
    assert isinstance(data, dict) and 'characters' in data

