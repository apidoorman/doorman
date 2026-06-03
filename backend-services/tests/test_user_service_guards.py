import pytest
from fastapi import HTTPException

from models.update_user_model import UpdateUserModel
from services import user_service as user_service_module
from services.user_service import UserService
from utils import password_util


@pytest.mark.asyncio
async def test_update_user_rejects_generic_password_updates(monkeypatch):
    monkeypatch.setattr(
        user_service_module.doorman_cache, 'get_cache', lambda cache_name, key: {'username': key}
    )
    monkeypatch.setattr(
        user_service_module.doorman_cache, 'delete_cache', lambda cache_name, key: None
    )

    async def _unexpected_db_update(*args, **kwargs):
        raise AssertionError('db_update_one should not run for generic password updates')

    monkeypatch.setattr(user_service_module, 'db_update_one', _unexpected_db_update)

    response = await UserService.update_user(
        'alice',
        UpdateUserModel(password='PlaintextPassword123!'),
        'req-123',
    )

    assert response['status_code'] == 400
    assert response['error_code'] == 'USR024'


@pytest.mark.asyncio
async def test_check_password_return_user_preserves_username_fallback(monkeypatch):
    async def _missing_email_user(email):
        raise HTTPException(status_code=404, detail='User not found')

    async def _lookup_by_username(collection, query):
        assert query == {'username': 'alice'}
        return {
            'username': 'alice',
            'password': password_util.hash_password('VeryStrongPassword123!'),
            'role': 'user',
        }

    monkeypatch.setattr(
        UserService, 'get_user_by_email_with_password_helper', staticmethod(_missing_email_user)
    )
    monkeypatch.setattr(user_service_module, 'db_find_one', _lookup_by_username)

    user = await UserService.check_password_return_user('alice', 'VeryStrongPassword123!')

    assert user['username'] == 'alice'


@pytest.mark.asyncio
async def test_check_password_return_user_propagates_backend_failures(monkeypatch):
    async def _backend_failure(email):
        raise RuntimeError('database unavailable')

    monkeypatch.setattr(
        UserService, 'get_user_by_email_with_password_helper', staticmethod(_backend_failure)
    )

    with pytest.raises(RuntimeError, match='database unavailable'):
        await UserService.check_password_return_user('alice@example.com', 'VeryStrongPassword123!')
