import time
import pytest

pytestmark = [pytest.mark.rest]

def test_endpoints_update_list_delete(client):
    api_name = f"epcrud-{int(time.time())}"
    api_version = 'v1'
    client.post('/platform/api', json={
        'api_name': api_name, 'api_version': api_version, 'api_description': 'ep',
        'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'], 'api_servers': ['http://127.0.0.1:9'], 'api_type': 'REST', 'active': True
    })
    client.post('/platform/endpoint', json={
        'api_name': api_name, 'api_version': api_version, 'endpoint_method': 'GET', 'endpoint_uri': '/z', 'endpoint_description': 'z'
    })
    r = client.put(f'/platform/endpoint/GET/{api_name}/{api_version}/z', json={'endpoint_description': 'zzz'})
    assert r.status_code in (200, 204)
    r = client.get(f'/platform/endpoint/{api_name}/{api_version}')
    assert r.status_code == 200
    eps = r.json().get('response', r.json())
    if isinstance(eps, dict) and 'endpoints' in eps:
        eps = eps['endpoints']
    assert isinstance(eps, list)
    r = client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/z')
    assert r.status_code in (200, 204)
    r = client.get(f'/api/rest/{api_name}/{api_version}/z')
    assert r.status_code in (404, 400, 500)
    client.delete(f'/platform/api/{api_name}/{api_version}')
