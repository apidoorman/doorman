import pytest


class _AuditSpy:
    def __init__(self):
        self.calls = []
    def info(self, msg):
        self.calls.append(msg)


@pytest.mark.asyncio
async def test_audit_api_create_update_delete(monkeypatch, authed_client):
    # Spy audit logger
    import utils.audit_util as au
    orig = au._logger
    spy = _AuditSpy()
    au._logger = spy
    try:
        # Create
        r = await authed_client.post('/platform/api', json={
            'api_name': 'aud1', 'api_version': 'v1', 'api_description': 'd',
            'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'],
            'api_servers': ['http://upstream'], 'api_type': 'REST', 'api_allowed_retry_count': 0,
        })
        assert r.status_code in (200, 201)
        # Update
        r = await authed_client.put('/platform/api/aud1/v1', json={'api_description': 'd2'})
        assert r.status_code == 200
        # Delete
        r = await authed_client.delete('/platform/api/aud1/v1')
        assert r.status_code in (200, 400)
        # Ensure audit logged something
        assert any('api.create' in c for c in spy.calls)
        assert any('api.update' in c for c in spy.calls)
        assert any('api.delete' in c for c in spy.calls)
    finally:
        au._logger = orig


@pytest.mark.asyncio
async def test_audit_user_credits_and_subscriptions(monkeypatch, authed_client):
    import utils.audit_util as au
    orig = au._logger
    spy = _AuditSpy()
    au._logger = spy
    try:
        # Save user credits
        r = await authed_client.post('/platform/credit/admin', json={'username': 'admin', 'users_credits': {}})
        assert r.status_code in (200, 201)
        # Subscribe & unsubscribe
        await authed_client.post('/platform/api', json={
            'api_name': 'aud2', 'api_version': 'v1', 'api_description': 'd',
            'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'],
            'api_servers': ['http://upstream'], 'api_type': 'REST', 'api_allowed_retry_count': 0,
        })
        r_me = await authed_client.get('/platform/user/me')
        username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
        r = await authed_client.post('/platform/subscription/subscribe', json={'username': username, 'api_name': 'aud2', 'api_version': 'v1'})
        assert r.status_code in (200, 201)
        r = await authed_client.post('/platform/subscription/unsubscribe', json={'username': username, 'api_name': 'aud2', 'api_version': 'v1'})
        assert r.status_code in (200, 201, 400)
        # Audit events present
        assert any('user_credits.save' in c for c in spy.calls)
        assert any('subscription.subscribe' in c for c in spy.calls)
        assert any('subscription.unsubscribe' in c for c in spy.calls)
    finally:
        au._logger = orig


@pytest.mark.asyncio
async def test_export_not_found_cases(authed_client):
    r = await authed_client.get('/platform/config/export/apis', params={'api_name': 'nope', 'api_version': 'v9'})
    assert r.status_code == 404
    r = await authed_client.get('/platform/config/export/roles', params={'role_name': 'nope-role'})
    assert r.status_code == 404
    r = await authed_client.get('/platform/config/export/groups', params={'group_name': 'nope-group'})
    assert r.status_code == 404
    r = await authed_client.get('/platform/config/export/routings', params={'client_key': 'nope-key'})
    assert r.status_code == 404

