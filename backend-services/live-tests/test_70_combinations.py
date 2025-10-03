import time
from servers import start_rest_echo_server


def test_endpoint_level_servers_override(client):
    srv_api = start_rest_echo_server()
    srv_ep = start_rest_echo_server()
    try:
        api_name = f'combo-{int(time.time())}'
        api_version = 'v1'

        # API with server A
        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'combo demo',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv_api.url],
            'api_type': 'REST',
            'active': True
        })
        assert r.status_code in (200, 201), r.text

        # Endpoint with server B
        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/who',
            'endpoint_description': 'who am i',
            'endpoint_servers': [srv_ep.url]
        })
        assert r.status_code in (200, 201), r.text

        # Subscribe admin
        r = client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})
        assert r.status_code in (200, 201)

        # Call gateway; verify upstream host:port matches the endpoint-level server rather than API-level
        r = client.get(f'/api/rest/{api_name}/{api_version}/who')
        assert r.status_code == 200
        data = r.json().get('response', r.json())
        headers = {k.lower(): v for k, v in (data.get('headers') or {}).items()}
        host_hdr = headers.get('host', '')
        # Extract host:port from srv_ep.url
        ep_hostport = srv_ep.url.replace('http://', '')
        assert host_hdr.endswith(ep_hostport)
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/who')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv_api.stop()
        srv_ep.stop()
import pytest
pytestmark = [pytest.mark.gateway, pytest.mark.routing]
