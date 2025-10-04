import time
from servers import start_rest_echo_server

def test_rest_gateway_basic_flow(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'rest-demo-{int(time.time())}'
        api_version = 'v1'

        api_payload = {
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'REST demo',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'active': True,
            'api_cors_allow_origins': ['*']
        }
        r = client.post('/platform/api', json=api_payload)
        assert r.status_code in (200, 201), r.text

        ep_payload = {
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/status',
            'endpoint_description': 'status'
        }
        r = client.post('/platform/endpoint', json=ep_payload)
        assert r.status_code in (200, 201), r.text

        sub_payload = {'api_name': api_name, 'api_version': api_version, 'username': 'admin'}
        r = client.post('/platform/subscription/subscribe', json=sub_payload)
        assert r.status_code in (200, 201), r.text

        r = client.get(f'/api/rest/{api_name}/{api_version}/status')
        assert r.status_code == 200, r.text
        data = r.json().get('response', r.json())
        assert data.get('method') == 'GET'
        assert data.get('path', '').endswith('/status')

        r = client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/status')
        assert r.status_code in (200, 204)
        r = client.delete(f'/platform/api/{api_name}/{api_version}')
        assert r.status_code in (200, 204)
    finally:
        srv.stop()

def test_rest_gateway_with_credits_and_header_injection(client):
    srv = start_rest_echo_server()
    try:
        ts = int(time.time())
        api_name = f'credit-demo-{ts}'
        api_version = 'v1'
        credit_group = f'cg-{ts}'
        api_key_val = 'DUMMY_API_KEY_ABC'

        r = client.post('/platform/credit', json={
            'api_credit_group': credit_group,
            'api_key': api_key_val,
            'api_key_header': 'x-api-key',
            'credit_tiers': [{ 'tier_name': 'default', 'credits': 2, 'input_limit': 0, 'output_limit': 0, 'reset_frequency': 'monthly' }]
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/credit/admin', json={
            'username': 'admin',
            'users_credits': { credit_group: { 'tier_name': 'default', 'available_credits': 2 } }
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'REST with credits',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'active': True,
            'api_credits_enabled': True,
            'api_credit_group': credit_group
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'POST',
            'endpoint_uri': '/echo',
            'endpoint_description': 'echo with header'
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})
        assert r.status_code in (200, 201), r.text

        r = client.post(f'/api/rest/{api_name}/{api_version}/echo', json={'ping': 'pong'})
        assert r.status_code == 200, r.text
        data = r.json().get('response', r.json())
        headers = {k.lower(): v for k, v in (data.get('headers') or {}).items()}
        assert headers.get('x-api-key') == api_key_val

        r = client.get('/platform/credit/admin')
        assert r.status_code == 200
        credits = r.json().get('response', r.json()).get('users_credits', {})
        assert credits.get(credit_group, {}).get('available_credits') in (1, 0)

    finally:
        try:
            client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/echo')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()
import pytest
pytestmark = [pytest.mark.rest, pytest.mark.gateway]
