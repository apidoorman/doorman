"""
Test that super admin user (username='admin') is a "ghost" - hidden from UI but functional.
Super admin should:
- Be able to authenticate and appear in logs
- Be completely hidden from all user list/get endpoints
- Be completely protected from modification/deletion via API
"""

import os

import pytest


@pytest.mark.asyncio
async def test_bootstrap_admin_can_authenticate(client):
    """Super admin should be able to authenticate normally."""
    email = os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
    password = os.getenv('DOORMAN_ADMIN_PASSWORD', 'SecPassword!12345')

    r = await client.post('/platform/authorization', json={'email': email, 'password': password})
    assert r.status_code == 200, 'Super admin should be able to authenticate'
    data = r.json()
    assert 'access_token' in (data.get('response') or data), 'Should receive access token'


@pytest.mark.asyncio
async def test_bootstrap_admin_hidden_from_user_list(authed_client):
    """Super admin (username='admin') should be visible to self."""
    r = await authed_client.get('/platform/user/all?page=1&page_size=100')
    assert r.status_code == 200

    users = r.json()
    user_list = (
        users
        if isinstance(users, list)
        else (users.get('users') or users.get('response', {}).get('users') or [])
    )
    usernames = {u.get('username') for u in user_list}

    assert 'admin' in usernames, 'Super admin should appear for admin user list'


@pytest.mark.asyncio
async def test_bootstrap_admin_get_by_username_returns_404(authed_client):
    """GET /platform/user/admin should return 200 for admin."""
    r = await authed_client.get('/platform/user/admin')
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_bootstrap_admin_get_by_email_returns_404(authed_client):
    """GET /platform/user/email/{email} should return 200 for admin."""
    email = os.getenv('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev')
    r = await authed_client.get(f'/platform/user/email/{email}')
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_bootstrap_admin_cannot_be_updated(authed_client):
    """PUT /platform/user/admin should be blocked."""
    r = await authed_client.put('/platform/user/admin', json={'email': 'new-email@example.com'})
    assert r.status_code == 403, 'Super admin should not be modifiable'
    data = r.json()
    assert 'USR020' in str(data.get('error_code')), 'Should return USR020 error code'
    assert 'super' in str(data.get('error_message')).lower(), 'Error message should mention super'


@pytest.mark.asyncio
async def test_bootstrap_admin_cannot_be_deleted(authed_client):
    """DELETE /platform/user/admin should be blocked."""
    r = await authed_client.delete('/platform/user/admin')
    assert r.status_code == 403, 'Super admin should not be deletable'
    data = r.json()
    assert 'USR021' in str(data.get('error_code')), 'Should return USR021 error code'
    assert 'super' in str(data.get('error_message')).lower(), 'Error message should mention super'


@pytest.mark.asyncio
async def test_bootstrap_admin_password_cannot_be_changed(authed_client):
    """PUT /platform/user/admin/update-password should be blocked."""
    r = await authed_client.put(
        '/platform/user/admin/update-password',
        json={'current_password': 'anything', 'new_password': 'NewPassword!123'},
    )
    assert r.status_code == 403, 'Super admin password should not be changeable via API'
    data = r.json()
    assert 'USR022' in str(data.get('error_code')), 'Should return USR022 error code'
    assert 'super' in str(data.get('error_message')).lower(), 'Error message should mention super'
