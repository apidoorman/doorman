import logging


def test_redaction_handles_cookies_csrf_and_mixed_cases():
    logger = logging.getLogger('doorman.gateway')
    filt = None
    for h in logger.handlers:
        if h.filters:
            filt = h.filters[0]
            break
    assert filt is not None

    secret = 'S3cr3t!'
    msg = (
        f'authorization: Bearer {secret}; Authorization: Bearer {secret}; '
        f'cookie: session={secret}; x-csrf-token: {secret}; PASSWORD="{secret}"'
    )
    rec = logging.LogRecord(
        name='doorman.gateway',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    assert filt.filter(rec) is True
    out = str(rec.msg)
    assert secret not in out

    assert out.lower().count('[redacted]') >= 3
