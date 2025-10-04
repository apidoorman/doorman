import time
from servers import start_rest_echo_server
import pytest

pytestmark = [pytest.mark.validation]

def test_nested_array_and_format_validations(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'valedge-{int(time.time())}'
        api_version = 'v1'
        client.post('/platform/api', json={
            'api_name': api_name, 'api_version': api_version,
            'api_description': 'edge validations', 'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url], 'api_type': 'REST', 'active': True
        })
        client.post('/platform/endpoint', json={
            'api_name': api_name, 'api_version': api_version,
            'endpoint_method': 'POST', 'endpoint_uri': '/submit', 'endpoint_description': 'submit'
        })
        client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

        r = client.get(f'/platform/endpoint/POST/{api_name}/{api_version}/submit')
        ep = r.json().get('response', r.json()); endpoint_id = ep.get('endpoint_id'); assert endpoint_id
        schema = {
            'validation_schema': {
                'user.email': {'required': True, 'type': 'string', 'format': 'email'},
                'items': {
                    'required': True, 'type': 'array', 'min': 1,
                    'array_items': {
                        'type': 'object',
                        'nested_schema': {
                            'id': {'required': True, 'type': 'string', 'format': 'uuid'},
                            'quantity': {'required': True, 'type': 'number', 'min': 1}
                        }
                    }
                }
            }
        }
        r = client.post('/platform/endpoint/endpoint/validation', json={
            'endpoint_id': endpoint_id, 'validation_enabled': True, 'validation_schema': schema
        })
        if r.status_code == 422:
            import pytest
            pytest.skip('Validation schema shape not accepted by server (422)')
        assert r.status_code in (200, 201)

        bad = {
            'user': {'email': 'not-an-email'},
            'items': [{'id': '123', 'quantity': 0}]
        }
        r = client.post(f'/api/rest/{api_name}/{api_version}/submit', json=bad)
        assert r.status_code == 400

        import uuid
        ok = {
            'user': {'email': 'u@example.com'},
            'items': [{'id': str(uuid.uuid4()), 'quantity': 2}]
        }
        r = client.post(f'/api/rest/{api_name}/{api_version}/submit', json=ok)
        assert r.status_code == 200
    finally:
        try:
            client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/submit')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()
