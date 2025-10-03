import time
import pytest

pytestmark = [pytest.mark.auth]


def test_subscribe_list_unsubscribe(client):
    api_name = f"subs-{int(time.time())}"
    api_version = 'v1'
    # Minimal API so subscription is meaningful
    client.post('/platform/api', json={
        'api_name': api_name,
        'api_version': api_version,
        'api_description': 'subs',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://127.0.0.1:9'],
        'api_type': 'REST',
        'active': True
    })
    # Subscribe admin
    r = client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})
    assert r.status_code in (200, 201), r.text
    # List subscriptions should include api
    r = client.get('/platform/subscription/subscriptions')
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    apis = payload.get('apis') or []
    assert any(f"{api_name}/{api_version}" == a for a in apis)
    # Unsubscribe
    r = client.post('/platform/subscription/unsubscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})
    assert r.status_code in (200, 201)
    # Cleanup
    client.delete(f'/platform/api/{api_name}/{api_version}')

