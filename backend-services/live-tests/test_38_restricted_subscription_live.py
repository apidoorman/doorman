import time

import pytest
from live_targets import GRAPHQL_TARGETS, GRPC_TARGETS, REST_TARGETS, SOAP_TARGETS
from client import LiveClient
pytestmark = [pytest.mark.public, pytest.mark.auth]


def _mk_api(
    client,
    name: str,
    ver: str,
    servers: list[str],
    api_type: str,
    extra: dict | None = None,
    allowed_roles: list[str] | None = None,
):
    r = client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'Restricted {name}',
            'api_servers': servers,
            'api_type': api_type,
            'api_public': False,
            'api_allowed_roles': allowed_roles or ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_allowed_retry_count': 0,
            'active': True,
            **(extra or {}),
        },
    )
    assert r.status_code in (200, 201), r.text


def _mk_endpoint(client, name: str, ver: str, method: str, uri: str):
    r = client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': method,
            'endpoint_uri': uri,
            'endpoint_description': f'{method} {uri}',
        },
    )
    if r.status_code not in (200, 201):
        try:
            b = r.json()
            if (b.get('error_code') or b.get('response', {}).get('error_code')) == 'END001':
                return
        except Exception:
            pass
        assert r.status_code in (200, 201), r.text


@pytest.fixture(scope='session')
def restricted_user(client):
    ts = int(time.time())
    role_name = f'sub_role_{ts}'
    r = client.post('/platform/role', json={'role_name': role_name})
    assert r.status_code in (200, 201), r.text

    uname = f'sub_user_{ts}'
    email = f'{uname}@example.com'
    pwd = 'Strong!Passw0rd1234'
    r = client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': email,
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
            'rate_limit_duration': 1000000,
            'rate_limit_duration_type': 'second',
            'throttle_duration': 1000000,
            'throttle_duration_type': 'second',
            'throttle_queue_limit': 1000000,
            'throttle_wait_duration': 0,
            'throttle_wait_duration_type': 'second',
        },
    )
    assert r.status_code in (200, 201), r.text
    uclient = LiveClient(client.base_url)
    uclient.login(email, pwd)
    try:
        yield {'client': uclient, 'username': uname, 'role': role_name}
    finally:
        try:
            uclient.cleanup()
        except Exception:
            pass


@pytest.fixture(scope='session')
def restricted_apis(client, restricted_user):
    ver = 'v1'
    stamp = str(int(time.time()))
    out = []
    allowed_roles = [restricted_user['role']]

    # REST (requires subscription)
    name = f'rx-rest-{stamp}'
    rest_server, rest_uri = REST_TARGETS[0]
    rest_path = rest_uri.split('?')[0] or '/'
    _mk_api(client, name, ver, [rest_server], 'REST', allowed_roles=allowed_roles)
    _mk_endpoint(client, name, ver, 'GET', rest_path)
    out.append(('REST', name, ver, {'uri': rest_uri}))

    # SOAP (requires subscription)
    name = f'rx-soap-{stamp}'
    soap_server, soap_uri, soap_kind, soap_action = SOAP_TARGETS[0]
    _mk_api(client, name, ver, [soap_server], 'SOAP', allowed_roles=allowed_roles)
    _mk_endpoint(client, name, ver, 'POST', soap_uri)
    out.append(
        ('SOAP', name, ver, {'uri': soap_uri, 'sk': soap_kind, 'soap_action': soap_action})
    )

    # GraphQL (requires subscription)
    name = f'rx-gql-{stamp}'
    gql_server, gql_query = GRAPHQL_TARGETS[0]
    _mk_api(client, name, ver, [gql_server], 'GRAPHQL', allowed_roles=allowed_roles)
    _mk_endpoint(client, name, ver, 'POST', '/graphql')
    out.append(('GRAPHQL', name, ver, {'query': gql_query}))

    # gRPC (requires subscription) — do not upload proto here; we only assert auth behavior
    name = f'rx-grpc-{stamp}'
    grpc_server, grpc_method = GRPC_TARGETS[0]
    _mk_api(
        client,
        name,
        ver,
        [grpc_server],
        'GRPC',
        extra=None,
        allowed_roles=allowed_roles,
    )
    _mk_endpoint(client, name, ver, 'POST', '/grpc')
    out.append(('GRPC', name, ver, {'method': grpc_method, 'message': {}}))

    try:
        yield out
    finally:
        # Teardown: delete endpoints and APIs to keep environment tidy
        for kind, name, ver, meta in list(out):
            try:
                if kind == 'GRPC':
                    client.delete(f'/platform/proto/{name}/{ver}')
            except Exception:
                pass
            try:
                if kind == 'REST':
                    method, uri = 'GET', meta['uri']
                elif kind == 'SOAP':
                    method, uri = 'POST', meta['uri']
                elif kind == 'GRAPHQL':
                    method, uri = 'POST', '/graphql'
                elif kind == 'GRPC':
                    method, uri = 'POST', '/grpc'
                else:
                    method, uri = 'GET', '/'
                client.delete(f'/platform/endpoint/{method}/{name}/{ver}{uri}')
            except Exception:
                pass
            try:
                client.post(
                    '/platform/subscription/unsubscribe',
                    json={'api_name': name, 'api_version': ver, 'username': 'admin'},
                )
            except Exception:
                pass
            try:
                client.delete(f'/platform/api/{name}/{ver}')
            except Exception:
                pass


def _call(client, kind: str, name: str, ver: str, meta: dict):
    if kind == 'REST':
        return client.get(f'/api/rest/{name}/{ver}{meta["uri"]}')
    if kind == 'SOAP':
        kind_key = meta.get('sk') or ''
        headers = {'Content-Type': 'text/xml'}
        if meta.get('soap_action'):
            headers['SOAPAction'] = meta['soap_action']
        if kind_key == 'calc':
            envelope = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><Add xmlns=\"http://tempuri.org/\"><intA>1</intA><intB>2</intB></Add>"
                "</soap:Body></soap:Envelope>"
            )
        elif kind_key == 'num':
            envelope = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><NumberToWords xmlns=\"http://www.dataaccess.com/webservicesserver/\">"
                "<ubiNum>7</ubiNum></NumberToWords></soap:Body></soap:Envelope>"
            )
        else:
            envelope = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
                "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" "
                "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">"
                "<soap:Body><CapitalCity xmlns=\"http://www.oorsprong.org/websamples.countryinfo\">"
                "<sCountryISOCode>US</sCountryISOCode></CapitalCity></soap:Body></soap:Envelope>"
            )
        return client.post(
            f'/api/soap/{name}/{ver}{meta["uri"]}', data=envelope, headers=headers
        )
    if kind == 'GRAPHQL':
        q = meta.get('query') or '{ __typename }'
        return client.post(
            f'/api/graphql/{name}', json={'query': q}, headers={'X-API-Version': ver}
        )
    if kind == 'GRPC':
        body = {'method': meta['method'], 'message': meta.get('message') or {}}
        return client.post(
            f'/api/grpc/{name}', json=body, headers={'X-API-Version': ver}
        )
    raise AssertionError('unknown kind')


@pytest.mark.parametrize('i', [0, 1, 2, 3])
def test_restricted_requires_subscription_then_allows(client, restricted_apis, restricted_user, i):
    kind, name, ver, meta = restricted_apis[i]
    uclient = restricted_user['client']
    uname = restricted_user['username']
    # Before subscription, should be blocked (401/403)
    r = _call(uclient, kind, name, ver, meta)
    assert r.status_code in (401, 403), r.text

    # Subscribe admin
    s = uclient.post(
        '/platform/subscription/subscribe',
        json={'api_name': name, 'api_version': ver, 'username': uname},
    )
    assert s.status_code in (200, 201) or (
        s.json().get('error_code') == 'SUB004'
    ), s.text

    # After subscription, avoid auth failure; tolerate upstream non-200
    r2 = _call(uclient, kind, name, ver, meta)
    assert r2.status_code not in (401, 403), r2.text


@pytest.mark.parametrize('i', [0, 1, 2, 3])
def test_restricted_unsubscribe_blocks(client, restricted_apis, restricted_user, i):
    kind, name, ver, meta = restricted_apis[i]
    uclient = restricted_user['client']
    uname = restricted_user['username']
    # Ensure subscribed first
    uclient.post(
        '/platform/subscription/subscribe',
        json={'api_name': name, 'api_version': ver, 'username': uname},
    )
    # Unsubscribe
    u = uclient.post(
        '/platform/subscription/unsubscribe',
        json={'api_name': name, 'api_version': ver, 'username': uname},
    )
    assert u.status_code in (200, 201) or (
        u.json().get('error_code') == 'SUB006'
    ), u.text

    # Now the call should be blocked again
    r = _call(uclient, kind, name, ver, meta)
    assert r.status_code in (401, 403), r.text
