import time

from servers import start_soap_echo_server


def test_soap_gateway_basic_flow(client):
    srv = start_soap_echo_server()
    try:
        api_name = f'soap-demo-{int(time.time())}'
        api_version = 'v1'

        r = client.post(
            '/platform/api',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'SOAP demo',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [srv.url],
                'api_type': 'REST',
                'api_allowed_retry_count': 0,
                'active': True,
            },
        )
        assert r.status_code in (200, 201), r.text

        r = client.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'POST',
                'endpoint_uri': '/soap',
                'endpoint_description': 'soap',
            },
        )
        assert r.status_code in (200, 201)

        r = client.post(
            '/platform/subscription/subscribe',
            json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
        )
        assert r.status_code in (200, 201)

        body = """
        <?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <EchoRequest><message>hi</message></EchoRequest>
          </soap:Body>
        </soap:Envelope>
        """.strip()
        r = client.post(
            f'/api/soap/{api_name}/{api_version}/soap',
            data=body,
            headers={'Content-Type': 'text/xml'},
        )
        assert r.status_code == 200, r.text
    finally:
        try:
            client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}/soap')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()


import pytest

pytestmark = [pytest.mark.soap, pytest.mark.gateway]
