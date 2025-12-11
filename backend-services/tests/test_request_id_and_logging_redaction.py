import logging
from io import StringIO

import pytest


@pytest.mark.asyncio
async def test_request_id_middleware_injects_header_when_missing(authed_client):
    r = await authed_client.get('/api/status')
    assert r.status_code == 200
    assert r.headers.get('X-Request-ID')


@pytest.mark.asyncio
async def test_request_id_middleware_preserves_existing_header(authed_client):
    r = await authed_client.get('/api/status', headers={'X-Request-ID': 'req-123'})
    assert r.status_code == 200
    assert r.headers.get('X-Request-ID') == 'req-123'


def _capture_logs(logger_name: str, message: str) -> str:
    logger = logging.getLogger(logger_name)
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    for h in logger.handlers:
        for f in getattr(h, 'filters', []):
            handler.addFilter(f)
    logger.addHandler(handler)
    logger.error(message)
    logger.removeHandler(handler)
    return stream.getvalue()


def test_logging_redacts_authorization_headers():
    msg = 'Authorization: Bearer secret-token'
    out = _capture_logs('doorman.gateway', msg)
    assert 'Authorization: [REDACTED]' in out


def test_logging_redacts_access_refresh_tokens():
    msg = 'access_token="abc123" refresh_token="def456"'
    out = _capture_logs('doorman.gateway', msg)
    assert 'access_token' in out and '[REDACTED]' in out


def test_logging_redacts_cookie_values():
    msg = 'cookie: sessionid=abcdef; csrftoken=xyz'
    out = _capture_logs('doorman.gateway', msg)
    assert 'cookie: [REDACTED]' in out
