import time

from servers import start_rest_echo_server


def test_rest_endpoint_validation_blocks_invalid_payload(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'val-{int(time.time())}'
        api_version = 'v1'

        r = client.post(
            '/platform/api',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'validation test',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [srv.url],
                'api_type': 'REST',
                'active': True,
            },
        )
        assert r.status_code in (200, 201)
        r = client.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'POST',
                'endpoint_uri': '/create',
                'endpoint_description': 'create',
            },
        )
        assert r.status_code in (200, 201)

        r = client.get(f'/platform/endpoint/POST/{api_name}/{api_version}/create')
        assert r.status_code == 200
        ep = r.json().get('response', r.json())
        endpoint_id = ep.get('endpoint_id')
        assert endpoint_id

        schema = {
            'validation_schema': {
                'user.name': {'required': True, 'type': 'string', 'min': 2},
                'user.age': {'required': True, 'type': 'number', 'min': 1},
            }
        }
        r = client.post(
            '/platform/endpoint/endpoint/validation',
            json={
                'endpoint_id': endpoint_id,
                'validation_enabled': True,
                'validation_schema': schema,
            },
        )
        assert r.status_code in (200, 201), r.text

        r = client.post(
            '/platform/subscription/subscribe',
            json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
        )
        assert r.status_code in (200, 201)

        r = client.post(f'/api/rest/{api_name}/{api_version}/create', json={'user': {'name': 'A'}})
        assert r.status_code == 400
        body = r.json()
        err = body.get('error_code') or body.get('response', {}).get('error_code')
        assert err == 'GTW011' or body.get('error_message')

        r = client.post(
            f'/api/rest/{api_name}/{api_version}/create', json={'user': {'name': 'Alan', 'age': 33}}
        )
        assert r.status_code == 200
    finally:
        try:
            client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/create')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()


import pytest

pytestmark = [pytest.mark.validation, pytest.mark.rest]
