# External imports
import pytest

@pytest.mark.asyncio
async def test_subscriptions_happy_and_invalid_payload(authed_client):

    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': 'subapi',
            'api_version': 'v1',
            'api_description': 'sub api',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://u'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    assert c.status_code in (200, 201)

    sub = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': 'subapi', 'api_version': 'v1'},
    )
    assert sub.status_code in (200, 201)

    ls = await authed_client.get('/platform/subscription/subscriptions')
    assert ls.status_code == 200

    us = await authed_client.post(
        '/platform/subscription/unsubscribe',
        json={'username': 'admin', 'api_name': 'subapi', 'api_version': 'v1'},
    )
    assert us.status_code in (200, 201)

    bad = await authed_client.post('/platform/subscription/subscribe', json={'username': 'admin'})
    assert bad.status_code in (400, 422)

