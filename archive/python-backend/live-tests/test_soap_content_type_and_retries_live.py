import pytest

from servers import start_soap_echo_server, start_soap_sequence_server


@pytest.mark.asyncio
async def test_soap_content_types_matrix(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    srv = start_soap_echo_server()
    try:
        name, ver = 'soapct', 'v1'
        await create_api(authed_client, name, ver)
        await authed_client.put(f'/platform/api/{name}/{ver}', json={'api_servers': [srv.url]})
        await create_endpoint(authed_client, name, ver, 'POST', '/s')
        await subscribe_self(authed_client, name, ver)

        for ct in ['application/xml', 'text/xml']:
            r = await authed_client.post(
                f'/api/soap/{name}/{ver}/s', headers={'Content-Type': ct}, content='<a/>'
            )
            assert r.status_code == 200
    finally:
        srv.stop()


@pytest.mark.asyncio
async def test_soap_retries_then_success(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    srv = start_soap_sequence_server([503, 200])
    try:
        name, ver = 'soaprt', 'v1'
        await create_api(authed_client, name, ver)
        await authed_client.put(f'/platform/api/{name}/{ver}', json={'api_servers': [srv.url]})
        await create_endpoint(authed_client, name, ver, 'POST', '/s')
        await subscribe_self(authed_client, name, ver)
        await authed_client.put(
            f'/platform/api/{name}/{ver}', json={'api_allowed_retry_count': 1}
        )
        await authed_client.delete('/api/caches')

        r = await authed_client.post(
            f'/api/soap/{name}/{ver}/s', headers={'Content-Type': 'application/xml'}, content='<a/>'
        )
        assert r.status_code == 200
    finally:
        srv.stop()
