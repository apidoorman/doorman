import time
import pytest

pytestmark = [pytest.mark.soap]

def test_soap_cors_preflight(client):
    api_name = f'soap-pre-{int(time.time())}'
    api_version = 'v1'
    client.post('/platform/api', json={
        'api_name': api_name, 'api_version': api_version, 'api_description': 'soap pre',
        'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'], 'api_servers': ['http://127.0.0.1:9'], 'api_type': 'REST', 'active': True,
        'api_cors_allow_origins': ['http://example.com'], 'api_cors_allow_methods': ['POST'], 'api_cors_allow_headers': ['Content-Type']
    })
    client.post('/platform/endpoint', json={
        'api_name': api_name, 'api_version': api_version, 'endpoint_method': 'POST', 'endpoint_uri': '/soap', 'endpoint_description': 's'
    })
    client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

    r = client.options(f'/api/soap/{api_name}/{api_version}/soap', headers={
        'Origin': 'http://example.com', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type'
    })
    assert r.status_code in (200, 204)
