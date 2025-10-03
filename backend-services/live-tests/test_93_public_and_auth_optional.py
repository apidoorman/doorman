import time
from servers import start_rest_echo_server
import requests


def test_public_api_no_auth_required(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'public-{int(time.time())}'
        api_version = 'v1'
        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'public',
            'api_allowed_roles': [],
            'api_allowed_groups': [],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'active': True,
            'api_public': True
        })
        assert r.status_code in (200, 201)
        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/status',
            'endpoint_description': 'status'
        })
        assert r.status_code in (200, 201)
        # Unauthenticated session
        s = requests.Session()
        url = client.base_url.rstrip('/') + f'/api/rest/{api_name}/{api_version}/status'
        r = s.get(url)
        assert r.status_code == 200
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/status')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()


def test_auth_not_required_but_not_public_allows_unauthenticated(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'authopt-{int(time.time())}'
        api_version = 'v1'
        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'auth optional',
            'api_allowed_roles': [],
            'api_allowed_groups': [],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'active': True,
            'api_public': False,
            'api_auth_required': False
        })
        assert r.status_code in (200, 201)
        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/ping',
            'endpoint_description': 'ping'
        })
        assert r.status_code in (200, 201)
        # Unauthenticated allowed
        import requests
        s = requests.Session()
        url = client.base_url.rstrip('/') + f'/api/rest/{api_name}/{api_version}/ping'
        r = s.get(url)
        assert r.status_code == 200
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/ping')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()
import pytest
pytestmark = [pytest.mark.rest, pytest.mark.auth]
