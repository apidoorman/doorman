import logging
from types import SimpleNamespace


def test_logging_redaction_filters_sensitive_values():
    # Retrieve the redaction filter attached to the logger's handler
    logger = logging.getLogger("doorman.gateway")
    filt = None
    for h in logger.handlers:
        if h.filters:
            filt = h.filters[0]
            break
    assert filt is not None, "Redaction filter not configured"

    # Create a synthetic log record and apply the filter without writing to disk
    secret = "supersecretvalue"
    record = logging.LogRecord(
        name="doorman.gateway", level=logging.INFO, pathname=__file__, lineno=1,
        msg=f"Authorization: Bearer {secret}; password=\"{secret}\"; access_token=\"{secret}\"", args=(), exc_info=None
    )
    ok = filt.filter(record)
    assert ok is True
    out = str(record.msg)
    assert secret not in out
    assert "[REDACTED]" in out
