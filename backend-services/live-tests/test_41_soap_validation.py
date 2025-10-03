import time
from servers import start_soap_echo_server


def test_soap_validation_blocks_missing_field(client):
    srv = start_soap_echo_server()
    try:
        api_name = f'soapval-{int(time.time())}'
        api_version = 'v1'
        # API + SOAP endpoint
        client.post('/platform/api', json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'soap val',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'active': True
        })
        client.post('/platform/endpoint', json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'POST',
            'endpoint_uri': '/soap',
            'endpoint_description': 'soap'
        })
        client.post('/platform/subscription/subscribe', json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'})

        # Get endpoint_id and attach validation requiring EchoRequest.message string min 2
        r = client.get(f'/platform/endpoint/POST/{api_name}/{api_version}/soap')
        ep = r.json().get('response', r.json()); endpoint_id = ep.get('endpoint_id'); assert endpoint_id
        schema = {
            'validation_schema': {
                # SOAP request_data uses the element's children directly; path is 'message'
                'message': { 'required': True, 'type': 'string', 'min': 2 }
            }
        }
        r = client.post('/platform/endpoint/endpoint/validation', json={
            'endpoint_id': endpoint_id, 'validation_enabled': True, 'validation_schema': schema
        })
        assert r.status_code in (200, 201)

        # Invalid payload (too short)
        xml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <EchoRequest><message>A</message></EchoRequest>
          </soap:Body>
        </soap:Envelope>
        """.strip()
        r = client.post(f'/api/soap/{api_name}/{api_version}/soap', data=xml, headers={'Content-Type': 'text/xml'})
        assert r.status_code == 400

        # Valid payload
        xml2 = xml.replace('>A<', '>AB<')
        r = client.post(f'/api/soap/{api_name}/{api_version}/soap', data=xml2, headers={'Content-Type': 'text/xml'})
        assert r.status_code == 200
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
