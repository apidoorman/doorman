import time
from servers import start_rest_echo_server

def test_client_routing_overrides_api_servers(client):
    srv_a = start_rest_echo_server()
    srv_b = start_rest_echo_server()
    try:
        api_name = f'route-{int(time.time())}'
        api_version = 'v1'
        client_key = f'ck-{int(time.time())}'

        r = client.post('/platform/routing', json={
            'routing_name': 'test-routing',
            'routing_servers': [srv_b.url],
            'routing_description': 'test',
            'client_key': client_key,
            'server_index': 0
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'routing demo',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv_a.url],
            'api_type': 'REST',
            'active': True
        })
        assert r.status_code in (200, 201)
        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/where',
            'endpoint_description': 'where'
        })
        assert r.status_code in (200, 201)

        client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

        r = client.get(f'/api/rest/{api_name}/{api_version}/where', headers={'client-key': client_key})
        assert r.status_code == 200
        data = r.json().get('response', r.json())
        hdrs = {k.lower(): v for k, v in (data.get('headers') or {}).items()}
        assert hdrs.get('host', '').endswith(srv_b.url.replace('http://', ''))
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/where')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        try:
            client.delete(f"/platform/routing/{client_key}")
        except Exception:
            pass
        srv_a.stop(); srv_b.stop()

def test_authorization_field_swap_sets_auth_header(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'authswap-{int(time.time())}'
        api_version = 'v1'
        swap_header = 'x-up-auth'
        token_value = 'Bearer SHHH_TOKEN'
        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'auth swap',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'active': True,
            'api_allowed_headers': [swap_header],
            'api_authorization_field_swap': swap_header
        })
        assert r.status_code in (200, 201)
        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/secure',
            'endpoint_description': 'secure'
        })
        assert r.status_code in (200, 201)
        client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

        r = client.get(f'/api/rest/{api_name}/{api_version}/secure', headers={swap_header: token_value})
        assert r.status_code == 200
        data = r.json().get('response', r.json())
        hdrs = {k.lower(): v for k, v in (data.get('headers') or {}).items()}
        assert hdrs.get('authorization') == token_value
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/secure')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()
import pytest
pytestmark = [pytest.mark.routing, pytest.mark.gateway]
