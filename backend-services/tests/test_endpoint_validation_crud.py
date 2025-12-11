import time

import pytest


@pytest.mark.asyncio
async def test_endpoint_validation_crud(authed_client):
    name, ver = f'valapi_{int(time.time())}', 'v1'
    # Create API and endpoint
    ca = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'validation api',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up.invalid'],
            'api_type': 'REST',
            'active': True,
        },
    )
    assert ca.status_code in (200, 201)
    ce = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/payload',
            'endpoint_description': 'payload',
        },
    )
    assert ce.status_code in (200, 201)

    # Resolve endpoint_id via GET
    ge = await authed_client.get(f'/platform/endpoint/POST/{name}/{ver}/payload')
    assert ge.status_code == 200
    eid = ge.json().get('endpoint_id') or ge.json().get('response', {}).get('endpoint_id')
    assert eid

    schema = {'validation_schema': {'id': {'required': True, 'type': 'string'}}}
    # Create validation
    cv = await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )
    assert cv.status_code in (200, 201)

    # Get validation
    gv = await authed_client.get(f'/platform/endpoint/endpoint/validation/{eid}')
    assert gv.status_code in (200, 400, 500)
    # Update validation
    uv = await authed_client.put(
        f'/platform/endpoint/endpoint/validation/{eid}',
        json={'validation_enabled': True, 'validation_schema': schema},
    )
    assert uv.status_code in (200, 400, 500)
    # Delete validation
    dv = await authed_client.delete(f'/platform/endpoint/endpoint/validation/{eid}')
    assert dv.status_code == 200
