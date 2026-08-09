import time

import pytest


@pytest.mark.asyncio
async def test_subscription_lifecycle(authed_client):
    name, ver = f'subapi_{int(time.time())}', 'v1'
    # Create API and endpoint
    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'sub api',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up.invalid'],
            'api_type': 'REST',
            'active': True,
        },
    )
    assert c.status_code in (200, 201)
    # Subscribe current user (admin)
    s = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'api_name': name, 'api_version': ver, 'username': 'admin'},
    )
    assert s.status_code in (200, 201)
    # List current user subscriptions
    ls = await authed_client.get('/platform/subscription/subscriptions')
    assert ls.status_code == 200
    # Unsubscribe
    u = await authed_client.post(
        '/platform/subscription/unsubscribe',
        json={'api_name': name, 'api_version': ver, 'username': 'admin'},
    )
    assert u.status_code == 200
