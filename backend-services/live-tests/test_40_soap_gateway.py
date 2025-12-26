import time

from live_targets import SOAP_TARGETS


def test_soap_gateway_basic_flow(client):
    last_error = None
    for idx, (server_url, uri, kind, action) in enumerate(SOAP_TARGETS):
        api_name = f'soap-demo-{int(time.time())}-{idx}'
        api_version = 'v1'
        try:
            r = client.post(
                '/platform/api',
                json={
                    'api_name': api_name,
                    'api_version': api_version,
                    'api_description': 'SOAP demo',
                    'api_allowed_roles': ['admin'],
                    'api_allowed_groups': ['ALL'],
                    'api_servers': [server_url],
                    'api_type': 'SOAP',
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
                    'endpoint_uri': uri,
                    'endpoint_description': 'soap',
                },
            )
            assert r.status_code in (200, 201)

            r = client.post(
                '/platform/subscription/subscribe',
                json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
            )
            assert r.status_code in (200, 201)

            if kind == 'calc':
                body = (
                    "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                    "<soap:Body><Add xmlns=\"http://tempuri.org/\"><intA>1</intA><intB>2</intB></Add>"
                    "</soap:Body></soap:Envelope>"
                )
            elif kind == 'num':
                body = (
                    "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                    "<soap:Body><NumberToWords xmlns=\"http://www.dataaccess.com/webservicesserver/\">"
                    "<ubiNum>7</ubiNum></NumberToWords></soap:Body></soap:Envelope>"
                )
            elif kind == 'temp':
                body = (
                    "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                    "<soap:Body><CelsiusToFahrenheit xmlns=\"https://www.w3schools.com/xml/\">"
                    "<Celsius>20</Celsius></CelsiusToFahrenheit></soap:Body></soap:Envelope>"
                )
            else:
                body = (
                    "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                    "<soap:Body><CapitalCity xmlns=\"http://www.oorsprong.org/websamples.countryinfo\">"
                    "<sCountryISOCode>US</sCountryISOCode></CapitalCity></soap:Body></soap:Envelope>"
                )
            headers = {'Content-Type': 'text/xml'}
            if action:
                headers['SOAPAction'] = action
            r = client.post(
                f'/api/soap/{api_name}/{api_version}{uri}',
                data=body,
                headers=headers,
            )
            if r.status_code == 200:
                return
            last_error = r
        finally:
            try:
                client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}{uri}')
            except Exception:
                pass
            try:
                client.delete(f'/platform/api/{api_name}/{api_version}')
            except Exception:
                pass

    assert last_error is None or last_error.status_code == 200, (
        last_error.text if last_error else 'No SOAP targets available'
    )


import pytest

pytestmark = [pytest.mark.soap, pytest.mark.gateway]
