import os
import time

import pytest
from config import ENABLE_GRAPHQL

pytestmark = pytest.mark.skipif(
    not ENABLE_GRAPHQL, reason='GraphQL test disabled (set DOORMAN_TEST_GRAPHQL=1 to enable)'
)


def test_graphql_gateway_basic_flow(client):
    try:
        import uvicorn
        from ariadne import QueryType, gql, make_executable_schema
        from ariadne.asgi import GraphQL
    except Exception as e:
        pytest.skip(f'Missing GraphQL deps: {e}')

    type_defs = gql("""
        type Query {
            hello(name: String): String!
        }
    """)
    query = QueryType()

    @query.field('hello')
    def resolve_hello(*_, name=None):
        return f'Hello, {name or "world"}!'

    schema = make_executable_schema(type_defs, query)
    app = GraphQL(schema, debug=True)

    import socket
    import threading

    def _find_port():
        s = socket.socket()
        s.bind(('0.0.0.0', 0))
        p = s.getsockname()[1]
        s.close()
        return p

    def _get_host_from_container():
        """Get the hostname to use when referring to the host machine from a Docker container."""
        import platform

        docker_env = os.getenv('DOORMAN_IN_DOCKER', '').lower()
        if docker_env in ('1', 'true', 'yes'):
            system = platform.system()
            if system == 'Darwin' or system == 'Windows':
                return 'host.docker.internal'
            else:
                return '172.17.0.1'
        return '127.0.0.1'

    port = _find_port()
    host = _get_host_from_container()
    config = uvicorn.Config(app, host='0.0.0.0', port=port, log_level='warning')
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    time.sleep(0.5)

    api_name = f'gql-demo-{int(time.time())}'
    api_version = 'v1'

    r = client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'GraphQL demo',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [f'http://{host}:{port}'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'active': True,
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
            'endpoint_description': 'graphql',
        },
    )
    assert r.status_code in (200, 201), r.text

    r = client.post(
        '/platform/subscription/subscribe',
        json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
    )
    assert r.status_code in (200, 201), r.text

    q = {'query': '{ hello(name:"Doorman") }'}
    r = client.post(f'/api/graphql/{api_name}', json=q, headers={'X-API-Version': api_version})
    assert r.status_code == 200, r.text
    data = r.json().get('response', r.json())
    if isinstance(data, dict) and 'data' in data:
        data = data['data']
    assert data.get('hello') == 'Hello, Doorman!'

    client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/graphql')
    client.delete(f'/platform/api/{api_name}/{api_version}')


import pytest

pytestmark = [pytest.mark.graphql, pytest.mark.gateway]
