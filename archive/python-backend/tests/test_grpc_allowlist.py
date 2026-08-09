import pytest


async def _setup_api_with_allowlist(
    client, name, ver, allowed_pkgs=None, allowed_svcs=None, allowed_methods=None
):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:50051'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    if allowed_pkgs is not None:
        payload['api_grpc_allowed_packages'] = allowed_pkgs
    if allowed_svcs is not None:
        payload['api_grpc_allowed_services'] = allowed_svcs
    if allowed_methods is not None:
        payload['api_grpc_allowed_methods'] = allowed_methods
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text
    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/grpc',
            'endpoint_description': 'grpc',
        },
    )
    assert r2.status_code in (200, 201), r2.text
    from conftest import subscribe_self

    await subscribe_self(client, name, ver)


@pytest.mark.asyncio
async def test_grpc_service_not_in_allowlist_returns_403(authed_client):
    name, ver = 'gallow1', 'v1'
    await _setup_api_with_allowlist(authed_client, name, ver, allowed_svcs=['Greeter'])
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': 'Admin.DeleteAll', 'message': {}},
    )
    assert r.status_code == 403
    body = r.json()
    assert body.get('error_code') == 'GTW013'


@pytest.mark.asyncio
async def test_grpc_method_not_in_allowlist_returns_403(authed_client):
    name, ver = 'gallow2', 'v1'
    await _setup_api_with_allowlist(authed_client, name, ver, allowed_methods=['Greeter.SayHello'])
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': 'Greeter.DeleteAll', 'message': {}},
    )
    assert r.status_code == 403
    body = r.json()
    assert body.get('error_code') == 'GTW013'


@pytest.mark.asyncio
async def test_grpc_package_not_in_allowlist_returns_403(authed_client):
    name, ver = 'gallow3', 'v1'
    await _setup_api_with_allowlist(authed_client, name, ver, allowed_pkgs=['goodpkg'])
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': 'Greeter.SayHello', 'message': {}, 'package': 'badpkg'},
    )
    assert r.status_code == 403
    body = r.json()
    assert body.get('error_code') == 'GTW013'


@pytest.mark.asyncio
async def test_grpc_invalid_traversal_rejected_400(authed_client):
    name, ver = 'gallow4', 'v1'
    await _setup_api_with_allowlist(authed_client, name, ver)
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': '../Evil', 'message': {}},
    )
    assert r.status_code == 400
    body = r.json()
    assert body.get('error_code') == 'GTW011'
