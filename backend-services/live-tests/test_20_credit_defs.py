import time

def test_credit_def_create_and_assign(client):
    group = f"credits_{int(time.time())}"
    api_key = 'TEST_API_KEY_123456789'
    payload = {
        'api_credit_group': group,
        'api_key': api_key,
        'api_key_header': 'x-api-key',
        'credit_tiers': [
            { 'tier_name': 'default', 'credits': 5, 'input_limit': 0, 'output_limit': 0, 'reset_frequency': 'monthly' }
        ]
    }
    r = client.post('/platform/credit', json=payload)
    assert r.status_code in (200, 201), r.text

    payload2 = {
        'username': 'admin',
        'users_credits': {
            group: {
                'tier_name': 'default',
                'available_credits': 5
            }
        }
    }
    r = client.post(f'/platform/credit/admin', json=payload2)
    assert r.status_code in (200, 201), r.text

    r = client.get(f'/platform/credit/defs/{group}')
    assert r.status_code == 200
    r = client.get('/platform/credit/admin')
    assert r.status_code == 200
    data = r.json().get('response', r.json())
    assert group in (data.get('users_credits') or {})
import pytest
pytestmark = [pytest.mark.credits]
