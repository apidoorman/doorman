import time

def test_single_api_export_import_roundtrip(client):
    api_name = f'cfg-{int(time.time())}'
    api_version = 'v1'
    client.post('/platform/api', json={
        'api_name': api_name,
        'api_version': api_version,
        'api_description': 'cfg demo',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://127.0.0.1:9'],
        'api_type': 'REST',
        'active': True
    })
    client.post('/platform/endpoint', json={
        'api_name': api_name,
        'api_version': api_version,
        'endpoint_method': 'GET',
        'endpoint_uri': '/x',
        'endpoint_description': 'x'
    })

    r = client.get(f'/platform/config/export/apis?api_name={api_name}&api_version={api_version}')
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    exported_api = payload.get('api'); exported_eps = payload.get('endpoints')
    assert exported_api and exported_api.get('api_name') == api_name
    assert any(ep.get('endpoint_uri') == '/x' for ep in (exported_eps or []))

    client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/x')
    client.delete(f'/platform/api/{api_name}/{api_version}')

    body = {'apis': [exported_api], 'endpoints': exported_eps}
    r = client.post('/platform/config/import', json=body)
    assert r.status_code == 200

    r = client.get(f'/platform/api/{api_name}/{api_version}')
    assert r.status_code == 200
    r = client.get(f'/platform/endpoint/GET/{api_name}/{api_version}/x')
    assert r.status_code == 200
import pytest
pytestmark = [pytest.mark.config]
