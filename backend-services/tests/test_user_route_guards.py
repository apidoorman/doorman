import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from models.create_user_model import CreateUserModel
from models.update_password_model import UpdatePasswordModel
from models.update_user_model import UpdateUserModel
from routes import user_routes
from utils.constants import ErrorCodes, Roles


def _request(path: str, method: str):
    return SimpleNamespace(
        client=SimpleNamespace(host='127.0.0.1', port=12345),
        method=method,
        url=SimpleNamespace(path=path),
    )


def _body(response):
    return json.loads(response.body.decode())


async def _unauthorized(*args, **kwargs):
    raise HTTPException(status_code=401, detail='Unauthorized')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('path', 'method', 'call'),
    [
        (
            '/platform/user',
            'POST',
            lambda request: user_routes.create_user(
                CreateUserModel(
                    username='alice',
                    email='alice@example.com',
                    password='VeryStrongPassword123!',
                    role='developer',
                    groups=['ALL'],
                    active=True,
                    ui_access=False,
                ),
                request,
            ),
        ),
        (
            '/platform/user/alice',
            'PUT',
            lambda request: user_routes.update_user(
                'alice',
                UpdateUserModel(email='newalice@example.com'),
                request,
            ),
        ),
        (
            '/platform/user/alice',
            'DELETE',
            lambda request: user_routes.delete_user('alice', request),
        ),
        (
            '/platform/user/alice/update-password',
            'PUT',
            lambda request: user_routes.update_user_password(
                'alice',
                UpdatePasswordModel(new_password='VeryStrongPassword123!'),
                request,
            ),
        ),
        (
            '/platform/user/alice',
            'GET',
            lambda request: user_routes.get_user_by_username('alice', request),
        ),
        (
            '/platform/user/email/alice@example.com',
            'GET',
            lambda request: user_routes.get_user_by_email('alice@example.com', request),
        ),
    ],
)
async def test_user_routes_preserve_http_auth_errors(monkeypatch, path, method, call):
    monkeypatch.setattr(user_routes, 'auth_required', _unauthorized)

    response = await call(_request(path, method))

    assert response.status_code == 401
    body = _body(response)
    assert body['error_code'] == ErrorCodes.HTTP_EXCEPTION
    assert body['error_message'] == 'Unauthorized'


@pytest.mark.asyncio
async def test_update_user_password_requires_current_password_for_self_service(monkeypatch):
    async def _auth_ok(request):
        return {'sub': 'alice'}

    monkeypatch.setattr(user_routes, 'auth_required', _auth_ok)

    response = await user_routes.update_user_password(
        'alice',
        UpdatePasswordModel(new_password='VeryStrongPassword123!'),
        _request('/platform/user/alice/update-password', 'PUT'),
    )

    assert response.status_code == 400
    body = _body(response)
    assert body['error_code'] == 'USR025'


@pytest.mark.asyncio
async def test_update_user_password_rejects_incorrect_current_password(monkeypatch):
    async def _auth_ok(request):
        return {'sub': 'alice'}

    async def _wrong_password(username, password):
        raise HTTPException(status_code=400, detail='Invalid email or password')

    async def _unexpected_update(*args, **kwargs):
        raise AssertionError('Password update should not run with an invalid current password')

    monkeypatch.setattr(user_routes, 'auth_required', _auth_ok)
    monkeypatch.setattr(
        user_routes.UserService,
        'check_password_return_user',
        staticmethod(_wrong_password),
    )
    monkeypatch.setattr(
        user_routes.UserService,
        'update_password',
        staticmethod(_unexpected_update),
    )

    response = await user_routes.update_user_password(
        'alice',
        UpdatePasswordModel(
            current_password='WrongPassword123!',
            new_password='VeryStrongPassword123!',
        ),
        _request('/platform/user/alice/update-password', 'PUT'),
    )

    assert response.status_code == 400
    body = _body(response)
    assert body['error_code'] == 'USR026'


@pytest.mark.asyncio
async def test_update_user_password_allows_admin_reset_without_current_password(monkeypatch):
    async def _auth_ok(request):
        return {'sub': 'manager'}

    async def _has_manage_users(username, action):
        assert username == 'manager'
        assert action == Roles.MANAGE_USERS
        return True

    async def _unexpected_password_check(*args, **kwargs):
        raise AssertionError('Current password should not be checked for admin resets')

    async def _update_password(username, update_data, request_id):
        assert username == 'alice'
        assert update_data.new_password == 'VeryStrongPassword123!'
        return {'status_code': 200, 'message': 'User updated successfully'}

    monkeypatch.setattr(user_routes, 'auth_required', _auth_ok)
    monkeypatch.setattr(user_routes, 'platform_role_required_bool', _has_manage_users)
    monkeypatch.setattr(
        user_routes.UserService,
        'check_password_return_user',
        staticmethod(_unexpected_password_check),
    )
    monkeypatch.setattr(
        user_routes.UserService,
        'update_password',
        staticmethod(_update_password),
    )

    response = await user_routes.update_user_password(
        'alice',
        UpdatePasswordModel(new_password='VeryStrongPassword123!'),
        _request('/platform/user/alice/update-password', 'PUT'),
    )

    assert response.status_code == 200
