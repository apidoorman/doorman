# External imports
import pytest

@pytest.mark.asyncio
async def test_api_crud_flow(authed_client):

    payload = {
        'api_name': 'customer',
        'api_version': 'v1',
        'api_description': 'Customer API',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.local'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    r = await authed_client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)

    g = await authed_client.get('/platform/api/customer/v1')
    assert g.status_code == 200
    gjson = g.json()
    assert gjson.get('api_name') == 'customer'
    assert gjson.get('api_version') == 'v1'

    lst = await authed_client.get('/platform/api/all?page=1&page_size=10')
    assert lst.status_code == 200
    apis = lst.json().get('apis', [])
    assert any(a.get('api_name') == 'customer' and a.get('api_version') == 'v1' for a in apis)

    upd = await authed_client.put(
        '/platform/api/customer/v1',
        json={'api_description': 'Customer API Updated'},
    )
    assert upd.status_code == 200

    ep_payload = {
        'api_name': 'customer',
        'api_version': 'v1',
        'endpoint_method': 'GET',
        'endpoint_uri': '/profile',
        'endpoint_description': 'Get profile',
    }
    cep = await authed_client.post('/platform/endpoint', json=ep_payload)
    assert cep.status_code in (200, 201)

    gep = await authed_client.get('/platform/endpoint/GET/customer/v1/profile')
    assert gep.status_code == 200
    assert gep.json().get('endpoint_method') == 'GET'

    le = await authed_client.get('/platform/endpoint/customer/v1')
    assert le.status_code == 200

    uep = await authed_client.put(
        '/platform/endpoint/GET/customer/v1/profile',
        json={'endpoint_description': 'Get customer profile'},
    )
    assert uep.status_code == 200

    dep = await authed_client.delete('/platform/endpoint/GET/customer/v1/profile')
    assert dep.status_code == 200

    d = await authed_client.delete('/platform/api/customer/v1')
    assert d.status_code == 200
