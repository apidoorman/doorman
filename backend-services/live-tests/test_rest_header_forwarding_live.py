import pytest

from servers import start_rest_echo_server, start_rest_headers_server


@pytest.mark.asyncio
async def test_forward_allowed_headers_only(authed_client):
    from conftest import create_endpoint, subscribe_self

    srv = start_rest_echo_server()
    try:
        name, ver = 'hforw', 'v1'
        payload = {
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_allowed_headers': ['x-allowed', 'content-type'],
        }
        await authed_client.post('/platform/api', json=payload)
        await create_endpoint(authed_client, name, ver, 'GET', '/p')
        await subscribe_self(authed_client, name, ver)

        r = await authed_client.get(
            f'/api/rest/{name}/{ver}/p', headers={'X-Allowed': 'yes', 'X-Blocked': 'no'}
        )
        assert r.status_code == 200
        data = r.json().get('response', r.json())
        headers = {k.lower(): v for k, v in (data.get('headers') or {}).items()}
        # Upstream should only receive allowed headers forwarded by gateway
        assert headers.get('x-allowed') == 'yes'
        assert 'x-blocked' not in headers
    finally:
        srv.stop()


@pytest.mark.asyncio
async def test_response_headers_filtered_by_allowlist(authed_client):
    from conftest import create_endpoint, subscribe_self

    # Upstream will send both headers; gateway should only forward allowed ones
    srv = start_rest_headers_server({'X-Upstream': 'yes', 'X-Secret': 'no'})
    try:
        name, ver = 'hresp', 'v1'
        payload = {
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_allowed_headers': ['x-upstream'],
        }
        await authed_client.post('/platform/api', json=payload)
        await create_endpoint(authed_client, name, ver, 'GET', '/p')
        await subscribe_self(authed_client, name, ver)

        r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
        assert r.status_code == 200
        # Only headers on allowlist should pass through
        assert r.headers.get('X-Upstream') == 'yes'
        assert 'X-Secret' not in r.headers
    finally:
        srv.stop()
