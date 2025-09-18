import os
from utils.auth_util import is_jwt_configured


def test_is_jwt_configured_true(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "abc123")
    assert is_jwt_configured() is True


def test_is_jwt_configured_false(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    assert is_jwt_configured() is False

