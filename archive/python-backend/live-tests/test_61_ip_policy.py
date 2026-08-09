import time

from servers import start_rest_echo_server


def _mk_api(client, srv_url, name, ver, ip_mode='allow_all', wl=None, bl=None, trust=True):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': [srv_url],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_ip_mode': ip_mode,
        'api_ip_whitelist': wl or [],
        'api_ip_blacklist': bl or [],
        'api_trust_x_forwarded_for': trust,
    }
    r = client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r = client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/p',
            'endpoint_description': 'p',
        },
    )
    assert r.status_code in (200, 201)
    r = client.post(
        '/platform/subscription/subscribe',
        json={'api_name': name, 'api_version': ver, 'username': 'admin'},
    )
    assert r.status_code in (200, 201) or (r.json().get('error_code') == 'SUB004')


def test_api_ip_whitelist_and_blacklist_live(client):
    srv = start_rest_echo_server()
    try:
        name, ver = f'ipwl-{int(time.time())}', 'v1'
        _mk_api(
            client,
            srv.url,
            name,
            ver,
            ip_mode='whitelist',
            wl=['1.2.3.4/32', '10.0.0.0/8'],
            bl=['8.8.8.8/32'],
            trust=True,
        )
        # Allowed exact
        r1 = client.get(
            f'/api/rest/{name}/{ver}/p', headers={'X-Real-IP': '1.2.3.4'}
        )
        assert r1.status_code == 200
        # Allowed CIDR
        r2 = client.get(
            f'/api/rest/{name}/{ver}/p', headers={'X-Real-IP': '10.23.45.6'}
        )
        assert r2.status_code == 200
        # Blacklisted
        r3 = client.get(
            f'/api/rest/{name}/{ver}/p', headers={'X-Real-IP': '8.8.8.8'}
        )
        assert r3.status_code == 403
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{name}/{ver}/p')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{name}/{ver}')
        except Exception:
            pass
        srv.stop()


def test_localhost_bypass_when_no_forward_headers_live(client):
    srv = start_rest_echo_server()
    try:
        name, ver = f'ipbypass-{int(time.time())}', 'v1'
        # Whitelist mode but empty list; with localhost and no forward headers, bypass applies
        _mk_api(client, srv.url, name, ver, ip_mode='whitelist', wl=[], bl=[], trust=True)
        r = client.get(f'/api/rest/{name}/{ver}/p')
        # When LOCAL_HOST_IP_BYPASS=true (default), expect allowed
        assert r.status_code in (200, 204)
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{name}/{ver}/p')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{name}/{ver}')
        except Exception:
            pass
        srv.stop()
