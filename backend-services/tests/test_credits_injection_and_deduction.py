import pytest
from tests.test_gateway_routing_limits import _FakeAsyncClient


async def _setup_api_with_credits(
    client,
    name='cr',
    ver='v1',
    public=False,
    group='g1',
    header='X-API-Key',
    def_key='DEFKEY',
    enable=True,
):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_credits_enabled': enable,
        'api_credit_group': group,
        'api_public': public,
    }
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/p',
            'endpoint_description': 'p',
        },
    )
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self

    await subscribe_self(client, name, ver)
    from utils.database import credit_def_collection

    credit_def_collection.delete_one({'api_credit_group': group})
    credit_def_collection.insert_one(
        {'api_credit_group': group, 'api_key_header': header, 'api_key': def_key}
    )
    return name, ver


def _set_user_credits(group: str, available: int, user_key: str | None = None):
    from utils.database import user_credit_collection

    user_credit_collection.delete_one({'username': 'admin'})
    doc = {
        'username': 'admin',
        'users_credits': {
            group: {'tier_name': 't', 'available_credits': available, 'user_api_key': user_key}
        },
    }
    user_credit_collection.insert_one(doc)


@pytest.mark.asyncio
async def test_credit_header_injected_when_enabled(monkeypatch, authed_client):
    name, ver = await _setup_api_with_credits(
        authed_client, name='cr1', public=False, group='g1', header='X-API-Key', def_key='DEF1'
    )
    _set_user_credits('g1', available=10, user_key=None)
    await authed_client.delete('/api/caches')
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200
    assert r.json().get('headers', {}).get('X-API-Key') == 'DEF1'


@pytest.mark.asyncio
async def test_credit_user_specific_overrides_default_key(monkeypatch, authed_client):
    name, ver = await _setup_api_with_credits(
        authed_client, name='cr2', public=False, group='g2', header='X-API-Key', def_key='DEF2'
    )
    _set_user_credits('g2', available=10, user_key='USERK')
    await authed_client.delete('/api/caches')
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200
    assert r.json().get('headers', {}).get('X-API-Key') == 'USERK'


@pytest.mark.asyncio
async def test_credit_not_deducted_for_public_api(monkeypatch, authed_client):
    name, ver = await _setup_api_with_credits(
        authed_client,
        name='cr3',
        public=True,
        group='g3',
        header='X-API-Key',
        def_key='DEF3',
        enable=False,
    )
    _set_user_credits('g3', available=5, user_key='U3')
    await authed_client.delete('/api/caches')
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200
    from utils.database import user_credit_collection

    doc = user_credit_collection.find_one({'username': 'admin'})
    assert doc['users_credits']['g3']['available_credits'] == 5


@pytest.mark.asyncio
async def test_credit_deducted_for_private_api_authenticated(monkeypatch, authed_client):
    name, ver = await _setup_api_with_credits(
        authed_client, name='cr4', public=False, group='g4', header='X-API-Key', def_key='DEF4'
    )
    _set_user_credits('g4', available=3, user_key='U4')
    await authed_client.delete('/api/caches')
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200
    from utils.database import user_credit_collection

    doc = user_credit_collection.find_one({'username': 'admin'})
    assert doc['users_credits']['g4']['available_credits'] == 2


@pytest.mark.asyncio
async def test_credit_deduction_insufficient_credits_blocks(monkeypatch, authed_client):
    name, ver = await _setup_api_with_credits(
        authed_client, name='cr5', public=False, group='g5', header='X-API-Key', def_key='DEF5'
    )
    _set_user_credits('g5', available=0, user_key=None)
    await authed_client.delete('/api/caches')
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 401
    body = r.json()
    assert body.get('error_code') == 'GTW008'
