import time

import pytest

pytestmark = [pytest.mark.rest]


def test_nonexistent_endpoint_returns_gw_error(client):
    api_name = f'gwerr-{int(time.time())}'
    api_version = 'v1'
    client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'gw',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://127.0.0.1:9'],
            'api_type': 'REST',
            'active': True,
        },
    )
    client.post(
        '/platform/subscription/subscribe',
        json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
    )
    r = client.get(f'/api/rest/{api_name}/{api_version}/nope')
    assert r.status_code in (404, 400, 500)
    data = r.json()
    code = data.get('error_code') or (data.get('response') or {}).get('error_code')
    assert code in ('GTW003', 'GTW001', 'GTW002', 'GTW006')
    client.delete(f'/platform/api/{api_name}/{api_version}')
