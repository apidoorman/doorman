import logging


def test_logging_redaction_filters_sensitive_values():
    logger = logging.getLogger('doorman.gateway')
    filt = None
    for h in logger.handlers:
        for f in h.filters:
            if type(f).__name__ == 'RedactFilter':
                filt = f
                break
        if filt:
            break
    assert filt is not None, 'Redaction filter not configured'

    secret = 'supersecretvalue'
    record = logging.LogRecord(
        name='doorman.gateway',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f'Authorization: Bearer {secret}; password="{secret}"; access_token="{secret}"',
        args=(),
        exc_info=None,
    )
    ok = filt.filter(record)
    assert ok is True
    out = str(record.msg)
    assert secret not in out
    assert '[REDACTED]' in out
