import logging
from io import StringIO


def _capture(logger_name: str, message: str) -> str:
    logger = logging.getLogger(logger_name)
    stream = StringIO()
    h = logging.StreamHandler(stream)
    for eh in logger.handlers:
        for f in getattr(eh, 'filters', []):
            h.addFilter(f)
    logger.addHandler(h)
    try:
        logger.info(message)
    finally:
        logger.removeHandler(h)
    return stream.getvalue()


def test_redacts_set_cookie_and_x_api_key():
    msg = (
        'Set-Cookie: access_token_cookie=abc123; Path=/; HttpOnly; Secure; X-API-Key: my-secret-key'
    )
    out = _capture('doorman.gateway', msg)
    assert 'Set-Cookie: [REDACTED]' in out or 'set-cookie: [REDACTED]' in out.lower()
    assert 'X-API-Key: [REDACTED]' in out or 'x-api-key: [REDACTED]' in out.lower()


def test_redacts_bearer_and_basic_tokens():
    msg = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhIn0.sgn; authorization: basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=='
    out = _capture('doorman.gateway', msg)
    low = out.lower()
    assert 'authorization: [redacted]' in low
    assert 'basic [redacted]' in low or 'authorization: [redacted]' in low
