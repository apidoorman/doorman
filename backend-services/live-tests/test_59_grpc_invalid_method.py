import time
import pytest
from config import ENABLE_GRPC

pytestmark = [pytest.mark.grpc]

def test_grpc_invalid_method_returns_error(client):
    if not ENABLE_GRPC:
        pytest.skip('gRPC disabled')
    try:
        import grpc_tools
    except Exception as e:
        pytest.skip(f'Missing gRPC deps: {e}')

    api_name = f'grpcbad{int(time.time())}'
    api_version = 'v1'
    proto = """
syntax = "proto3";
package {pkg};
service Greeter {}
""".replace('{pkg}', f'{api_name}_{api_version}')
    r = client.post(f'/platform/proto/{api_name}/{api_version}', files={'file': ('s.proto', proto.encode('utf-8'))})
    assert r.status_code == 200
    client.post('/platform/api', json={
        'api_name': api_name, 'api_version': api_version, 'api_description': 'g', 'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'], 'api_servers': ['grpc://127.0.0.1:9'], 'api_type': 'REST', 'active': True
    })
    client.post('/platform/endpoint', json={
        'api_name': api_name, 'api_version': api_version, 'endpoint_method': 'POST', 'endpoint_uri': '/grpc', 'endpoint_description': 'g'
    })
    client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})
    r = client.post(f'/api/grpc/{api_name}', json={'method': 'Nope.Do', 'message': {}}, headers={'X-API-Version': api_version})
    assert r.status_code in (404, 500)
