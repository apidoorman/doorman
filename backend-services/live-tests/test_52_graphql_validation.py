import time

import pytest
from config import ENABLE_GRAPHQL

pytestmark = pytest.mark.skipif(
    not ENABLE_GRAPHQL, reason='GraphQL validation test disabled (set DOORMAN_TEST_GRAPHQL=1)'
)


def test_graphql_validation_blocks_invalid_variables(client):
    try:
        import uvicorn
        from ariadne import QueryType, gql, make_executable_schema
        from ariadne.asgi import GraphQL
    except Exception as e:
        pytest.skip(f'Missing GraphQL deps: {e}')

    type_defs = gql("""
        type Query { hello(name: String!): String! }
    """)
    query = QueryType()

    @query.field('hello')
    def resolve_hello(*_, name):
        return f'Hello, {name}!'

    schema = make_executable_schema(type_defs, query)
    import platform
    import socket
    import threading

    import uvicorn

    def _free_port():
        s = socket.socket()
        s.bind(('0.0.0.0', 0))
        p = s.getsockname()[1]
        s.close()
        return p

    def _get_host_from_container():
        import os

        docker_env = os.getenv('DOORMAN_IN_DOCKER', '').lower()
        if docker_env in ('1', 'true', 'yes'):
            system = platform.system()
            if system == 'Darwin' or system == 'Windows':
                return 'host.docker.internal'
            else:
                return '172.17.0.1'
        return '127.0.0.1'

    port = _free_port()
    host = _get_host_from_container()
    server = uvicorn.Server(
        uvicorn.Config(GraphQL(schema), host='0.0.0.0', port=port, log_level='warning')
    )
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(0.4)

    api_name = f'gqlval-{int(time.time())}'
    api_version = 'v1'
    client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'gql val',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [f'http://{host}:{port}'],
            'api_type': 'REST',
            'active': True,
        },
    )
    client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'POST',
            'endpoint_uri': '/graphql',
            'endpoint_description': 'gql',
        },
    )
    client.post(
        '/platform/subscription/subscribe',
        json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
    )

    r = client.get(f'/platform/endpoint/POST/{api_name}/{api_version}/graphql')
    ep = r.json().get('response', r.json())
    endpoint_id = ep.get('endpoint_id')
    assert endpoint_id

    schema = {'validation_schema': {'HelloOp.x': {'required': True, 'type': 'string', 'min': 2}}}
    r = client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': endpoint_id, 'validation_enabled': True, 'validation_schema': schema},
    )
    assert r.status_code in (200, 201)

    q = {'query': 'query HelloOp($x: String!) { hello(name: $x) }', 'variables': {'x': 'A'}}
    r = client.post(f'/api/graphql/{api_name}', json=q, headers={'X-API-Version': api_version})
    assert r.status_code == 400

    q['variables'] = {'x': 'Alan'}
    r = client.post(f'/api/graphql/{api_name}', json=q, headers={'X-API-Version': api_version})
    assert r.status_code == 200
