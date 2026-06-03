import pytest
from fastapi import HTTPException

from routes import config_hot_reload_routes


@pytest.mark.asyncio
async def test_get_current_config_uses_live_manage_gateway_permission(monkeypatch):
    async def _deny_manage_gateway(username, action):
        assert username == 'alice'
        assert action == 'manage_gateway'
        return False

    monkeypatch.setattr(
        config_hot_reload_routes,
        'platform_role_required_bool',
        _deny_manage_gateway,
    )

    with pytest.raises(HTTPException) as exc_info:
        await config_hot_reload_routes.get_current_config(
            {'sub': 'alice', 'accesses': {'manage_gateway': True}}
        )

    assert exc_info.value.status_code == 403
    assert 'manage_gateway required' in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_trigger_config_reload_uses_live_manage_gateway_permission(monkeypatch):
    async def _deny_manage_gateway(username, action):
        assert username == 'alice'
        assert action == 'manage_gateway'
        return False

    monkeypatch.setattr(
        config_hot_reload_routes,
        'platform_role_required_bool',
        _deny_manage_gateway,
    )

    with pytest.raises(HTTPException) as exc_info:
        await config_hot_reload_routes.trigger_config_reload(
            {'sub': 'alice', 'accesses': {'manage_gateway': True}}
        )

    assert exc_info.value.status_code == 403
    assert 'manage_gateway required' in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_config_succeeds_with_live_manage_gateway_permission(monkeypatch):
    async def _allow_manage_gateway(username, action):
        assert username == 'alice'
        assert action == 'manage_gateway'
        return True

    monkeypatch.setattr(
        config_hot_reload_routes,
        'platform_role_required_bool',
        _allow_manage_gateway,
    )
    monkeypatch.setattr(config_hot_reload_routes.hot_config, 'dump', lambda: {'LOG_LEVEL': 'INFO'})

    response = await config_hot_reload_routes.get_current_config({'sub': 'alice'})

    assert response['status_code'] == 200
    assert response['response']['config'] == {'LOG_LEVEL': 'INFO'}
