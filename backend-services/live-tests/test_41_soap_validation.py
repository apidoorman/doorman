import time

from live_targets import SOAP_TARGETS


def test_soap_validation_blocks_missing_field(client):
    try:
        api_name = f'soapval-{int(time.time())}'
        api_version = 'v1'
        server_url, uri, kind, action = SOAP_TARGETS[0]
        client.post(
            '/platform/api',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'soap val',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [server_url],
                'api_type': 'SOAP',
                'active': True,
            },
        )
        client.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'POST',
                'endpoint_uri': uri,
                'endpoint_description': 'soap',
            },
        )
        client.post(
            '/platform/subscription/subscribe',
            json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
        )

        r = client.get(f'/platform/endpoint/POST/{api_name}/{api_version}{uri}')
        ep = r.json().get('response', r.json())
        endpoint_id = ep.get('endpoint_id')
        assert endpoint_id
        if kind == 'num':
            schema_field = 'ubiNum'
        elif kind == 'temp':
            schema_field = 'Celsius'
        elif kind == 'country':
            schema_field = 'sCountryISOCode'
        else:
            schema_field = 'intA'
        schema = {'validation_schema': {schema_field: {'required': True, 'type': 'string', 'min': 2}}}
        r = client.post(
            '/platform/endpoint/endpoint/validation',
            json={
                'endpoint_id': endpoint_id,
                'validation_enabled': True,
                'validation_schema': schema,
            },
        )
        assert r.status_code in (200, 201)

        if kind == 'calc':
            xml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><Add xmlns=\"http://tempuri.org/\"><intA>1</intA><intB>2</intB></Add>"
                "</soap:Body></soap:Envelope>"
            )
        elif kind == 'num':
            xml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><NumberToWords xmlns=\"http://www.dataaccess.com/webservicesserver/\">"
                "<ubiNum>7</ubiNum></NumberToWords></soap:Body></soap:Envelope>"
            )
        elif kind == 'temp':
            xml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><CelsiusToFahrenheit xmlns=\"https://www.w3schools.com/xml/\">"
                "<Celsius>1</Celsius></CelsiusToFahrenheit></soap:Body></soap:Envelope>"
            )
        elif kind == 'country':
            xml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><CapitalCity xmlns=\"http://www.oorsprong.org/websamples.countryinfo\">"
                "<sCountryISOCode>U</sCountryISOCode></CapitalCity></soap:Body></soap:Envelope>"
            )
        else:
            xml = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><Add xmlns=\"http://tempuri.org/\"><intA>1</intA><intB>2</intB></Add>"
                "</soap:Body></soap:Envelope>"
            )
        headers = {'Content-Type': 'text/xml'}
        if action:
            if action.startswith('"') and action.endswith('"'):
                headers['SOAPAction'] = action
            else:
                headers['SOAPAction'] = f'"{action}"'
        r = client.post(
            f'/api/soap/{api_name}/{api_version}{uri}',
            data=xml,
            headers=headers,
        )
        assert r.status_code == 400

        if kind == 'num':
            xml2 = xml.replace('<ubiNum>7</ubiNum>', '<ubiNum>12</ubiNum>')
        elif kind == 'temp':
            xml2 = xml.replace('<Celsius>1</Celsius>', '<Celsius>20</Celsius>')
        elif kind == 'country':
            xml2 = xml.replace('<sCountryISOCode>U</sCountryISOCode>', '<sCountryISOCode>US</sCountryISOCode>')
        else:
            xml2 = xml.replace('<intA>1</intA>', '<intA>12</intA>')
        r = client.post(
            f'/api/soap/{api_name}/{api_version}{uri}',
            data=xml2,
            headers=headers,
        )
        assert r.status_code in (200, 401, 403, 404, 500, 502, 503, 504)
    finally:
        try:
            client.delete(f'/platform/endpoint/POST/{api_name}/{api_version}{uri}')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
