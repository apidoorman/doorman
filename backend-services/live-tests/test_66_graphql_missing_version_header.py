import time
import pytest
from config import ENABLE_GRAPHQL

pytestmark = [pytest.mark.graphql]

def test_graphql_missing_version_header_returns_400(client):
    if not ENABLE_GRAPHQL:
        pytest.skip('GraphQL disabled')
    try:
        from ariadne import gql, make_executable_schema, QueryType
        from ariadne.asgi import GraphQL
        import uvicorn
    except Exception as e:
        pytest.skip(f'Missing deps: {e}')

    type_defs = gql('type Query { ok: String! }')
    query = QueryType()
    @query.field('ok')
    def resolve_ok(*_):
        return 'ok'
    schema = make_executable_schema(type_defs, query)
    import threading, socket
    s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
    server = uvicorn.Server(uvicorn.Config(GraphQL(schema), host='127.0.0.1', port=port, log_level='warning'))
    t = threading.Thread(target=server.run, daemon=True); t.start()
    import time as _t; _t.sleep(0.4)

    api_name = f'gql-novh-{int(time.time())}'
    api_version = 'v1'
    client.post('/platform/api', json={
        'api_name': api_name, 'api_version': api_version, 'api_description': 'gql',
        'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'], 'api_servers': [f'http://127.0.0.1:{port}'], 'api_type': 'REST', 'active': True
    })
    client.post('/platform/endpoint', json={
        'api_name': api_name, 'api_version': api_version, 'endpoint_method': 'POST', 'endpoint_uri': '/graphql', 'endpoint_description': 'gql'
    })
    client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

    r = client.post(f'/api/graphql/{api_name}', json={'query': '{ ok }'})
    assert r.status_code == 400
