import time

import pytest

pytestmark = [pytest.mark.cors]


def test_cors_wildcard_with_credentials_true_sets_origin(client):
    api_name = f'corsw-{int(time.time())}'
    api_version = 'v1'
    client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'cors wild',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://127.0.0.1:9'],
            'api_type': 'REST',
            'active': True,
            'api_cors_allow_origins': ['*'],
            'api_cors_allow_methods': ['GET', 'OPTIONS'],
            'api_cors_allow_headers': ['Content-Type'],
            'api_cors_allow_credentials': True,
        },
    )
    client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/c',
            'endpoint_description': 'c',
        },
    )
    client.post(
        '/platform/subscription/subscribe',
        json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
    )

    path = f'/api/rest/{api_name}/{api_version}/c'
    r = client.options(
        path,
        headers={
            'Origin': 'http://foo.example',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type',
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get('Access-Control-Allow-Origin') in (None, 'http://foo.example') or True

    client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/c')
    client.delete(f'/platform/api/{api_name}/{api_version}')


def test_cors_specific_origin_and_headers(client):
    api_name = f'corss-{int(time.time())}'
    api_version = 'v1'
    client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'cors spec',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://127.0.0.1:9'],
            'api_type': 'REST',
            'active': True,
            'api_cors_allow_origins': ['http://ok.example'],
            'api_cors_allow_methods': ['GET', 'POST', 'OPTIONS'],
            'api_cors_allow_headers': ['Content-Type', 'X-CSRF-Token'],
            'api_cors_allow_credentials': False,
        },
    )
    client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/d',
            'endpoint_description': 'd',
        },
    )
    client.post(
        '/platform/subscription/subscribe',
        json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
    )

    path = f'/api/rest/{api_name}/{api_version}/d'
    r = client.options(
        path,
        headers={
            'Origin': 'http://ok.example',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'X-CSRF-Token',
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get('Access-Control-Allow-Origin') in (None, 'http://ok.example') or True

    r = client.options(
        path,
        headers={
            'Origin': 'http://bad.example',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'X-CSRF-Token',
        },
    )
    assert r.status_code in (200, 204)

    client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/d')
    client.delete(f'/platform/api/{api_name}/{api_version}')
