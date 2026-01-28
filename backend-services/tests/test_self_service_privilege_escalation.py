"""
Tests for self-service profile update privilege escalation prevention.

CVE fix: Users without manage_users permission should not be able to modify
restricted fields (role, groups, active, username) when updating their own profile.

These are integration tests that use the actual application fixtures.
"""

import pytest


@pytest.mark.asyncio
async def test_regular_user_cannot_change_own_role(authed_client):
    """User cannot escalate privileges by changing their own role."""
    # Create a role without manage_users
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'limited', 'role_description': 'Limited user', 'manage_users': False}
    )
    
    # Create user with the limited role
    await authed_client.post(
        '/platform/user',
        json={
            'username': 'privesc_test_user',
            'email': 'privesc@doorman.dev',
            'password': 'SecurePassword123!',
            'role': 'limited',
            'active': True,
        }
    )
    
    # Login as that limited user
    from doorman import doorman
    from httpx import AsyncClient
    import os
    
    user_client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await user_client.post(
        '/platform/authorization',
        json={'email': 'privesc@doorman.dev', 'password': 'SecurePassword123!'}
    )
    assert r.status_code == 200
    body = r.json()
    token = body.get('access_token')
    if token:
        user_client.cookies.set(
            'access_token_cookie',
            token,
            domain=os.environ.get('COOKIE_DOMAIN') or 'testserver',
            path='/',
        )
    
    # Attempt privilege escalation: change own role to admin
    resp = await user_client.put(
        '/platform/user/privesc_test_user',
        json={'role': 'admin'}
    )
    
    assert resp.status_code == 403, f'Expected 403, got {resp.status_code}: {resp.text}'
    data = resp.json()
    assert data.get('error_code') == 'USR023'
    assert 'role' in data.get('error_message', '').lower()


@pytest.mark.asyncio
async def test_regular_user_cannot_change_own_groups(authed_client):
    """User cannot escalate privileges by adding themselves to privileged groups."""
    # Create a role without manage_users
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'limited2', 'role_description': 'Limited user', 'manage_users': False}
    )
    
    # Create user with the limited role
    await authed_client.post(
        '/platform/user',
        json={
            'username': 'privesc_test_groups',
            'email': 'privesc_groups@doorman.dev',
            'password': 'SecurePassword123!',
            'role': 'limited2',
            'active': True,
        }
    )
    
    # Login as that limited user
    from doorman import doorman
    from httpx import AsyncClient
    import os
    
    user_client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await user_client.post(
        '/platform/authorization',
        json={'email': 'privesc_groups@doorman.dev', 'password': 'SecurePassword123!'}
    )
    assert r.status_code == 200
    body = r.json()
    token = body.get('access_token')
    if token:
        user_client.cookies.set(
            'access_token_cookie',
            token,
            domain=os.environ.get('COOKIE_DOMAIN') or 'testserver',
            path='/',
        )
    
    # Attempt privilege escalation: add self to all groups
    resp = await user_client.put(
        '/platform/user/privesc_test_groups',
        json={'groups': ['ALL', 'admin-group']}
    )
    
    assert resp.status_code == 403, f'Expected 403, got {resp.status_code}: {resp.text}'
    data = resp.json()
    assert data.get('error_code') == 'USR023'
    assert 'groups' in data.get('error_message', '').lower()


@pytest.mark.asyncio
async def test_regular_user_cannot_change_own_active_status(authed_client):
    """User cannot modify their own active status without manage_users."""
    # Create a role without manage_users
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'limited3', 'role_description': 'Limited user', 'manage_users': False}
    )
    
    # Create user with the limited role
    await authed_client.post(
        '/platform/user',
        json={
            'username': 'privesc_test_active',
            'email': 'privesc_active@doorman.dev',
            'password': 'SecurePassword123!',
            'role': 'limited3',
            'active': True,
        }
    )
    
    # Login as that limited user
    from doorman import doorman
    from httpx import AsyncClient
    import os
    
    user_client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await user_client.post(
        '/platform/authorization',
        json={'email': 'privesc_active@doorman.dev', 'password': 'SecurePassword123!'}
    )
    assert r.status_code == 200
    body = r.json()
    token = body.get('access_token')
    if token:
        user_client.cookies.set(
            'access_token_cookie',
            token,
            domain=os.environ.get('COOKIE_DOMAIN') or 'testserver',
            path='/',
        )
    
    # Attempt privilege escalation: change own active flag
    resp = await user_client.put(
        '/platform/user/privesc_test_active',
        json={'active': False}
    )
    
    assert resp.status_code == 403, f'Expected 403, got {resp.status_code}: {resp.text}'
    data = resp.json()
    assert data.get('error_code') == 'USR023'
    assert 'active' in data.get('error_message', '').lower()


@pytest.mark.asyncio
async def test_regular_user_can_change_own_email(authed_client):
    """User CAN change their own email without manage_users (allowed field)."""
    # Create a role without manage_users
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'limited4', 'role_description': 'Limited user', 'manage_users': False}
    )
    
    # Create user with the limited role
    await authed_client.post(
        '/platform/user',
        json={
            'username': 'privesc_test_email',
            'email': 'privesc_email@doorman.dev',
            'password': 'SecurePassword123!',
            'role': 'limited4',
            'active': True,
        }
    )
    
    # Login as that limited user
    from doorman import doorman
    from httpx import AsyncClient
    import os
    
    user_client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await user_client.post(
        '/platform/authorization',
        json={'email': 'privesc_email@doorman.dev', 'password': 'SecurePassword123!'}
    )
    assert r.status_code == 200
    body = r.json()
    token = body.get('access_token')
    if token:
        user_client.cookies.set(
            'access_token_cookie',
            token,
            domain=os.environ.get('COOKIE_DOMAIN') or 'testserver',
            path='/',
        )
    
    # Change own email - should be ALLOWED
    resp = await user_client.put(
        '/platform/user/privesc_test_email',
        json={'email': 'new_email@doorman.dev'}
    )
    
    assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.text}'


@pytest.mark.asyncio
async def test_admin_can_change_any_user_role(authed_client):
    """Admin with manage_users CAN change another user's role."""
    # Create a limited role
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'target_role', 'role_description': 'Target user', 'manage_users': False}
    )
    
    # Create a target user
    await authed_client.post(
        '/platform/user',
        json={
            'username': 'target_user',
            'email': 'target@doorman.dev',
            'password': 'SecurePassword123!',
            'role': 'target_role',
            'active': True,
        }
    )
    
    # Admin (authed_client) changes target user's role - should be ALLOWED
    resp = await authed_client.put(
        '/platform/user/target_user',
        json={'role': 'admin'}
    )
    
    assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.text}'
