import time
from servers import start_rest_echo_server

def test_user_specific_credit_api_key_overrides_group_key(client):
    srv = start_rest_echo_server()
    try:
        ts = int(time.time())
        api_name = f'cred-override-{ts}'
        api_version = 'v1'
        group = f'cg-ovr-{ts}'
        group_key = 'GROUP_KEY_ABC'
        user_key = 'USER_KEY_DEF'

        r = client.post('/platform/credit', json={
            'api_credit_group': group,
            'api_key': group_key,
            'api_key_header': 'x-api-key',
            'credit_tiers': [{ 'tier_name': 'default', 'credits': 3, 'input_limit': 0, 'output_limit': 0, 'reset_frequency': 'monthly' }]
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/credit/admin', json={
            'username': 'admin',
            'users_credits': { group: { 'tier_name': 'default', 'available_credits': 3, 'user_api_key': user_key } }
        })
        assert r.status_code in (200, 201), r.text

        r = client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'credit user override',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'active': True,
            'api_credits_enabled': True,
            'api_credit_group': group
        })
        assert r.status_code in (200, 201), r.text
        r = client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/whoami',
            'endpoint_description': 'whoami'
        })
        assert r.status_code in (200, 201), r.text
        client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

        r = client.get(f'/api/rest/{api_name}/{api_version}/whoami')
        assert r.status_code == 200
        data = r.json().get('response', r.json())
        headers = {k.lower(): v for k, v in (data.get('headers') or {}).items()}
        assert headers.get('x-api-key') == user_key
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/whoami')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()
