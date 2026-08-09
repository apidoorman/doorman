"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import uuid
from contextvars import ContextVar

correlation_id: ContextVar[str | None] = ContextVar('correlation_id', default=None)

logger = logging.getLogger('doorman.gateway')


def get_correlation_id() -> str | None:
    """
    Get the current correlation ID from context.
    """
    return correlation_id.get()


def set_correlation_id(value: str) -> None:
    """
    Set the correlation ID in the current context.
    """
    correlation_id.set(value)


def ensure_correlation_id() -> str:
    """
    Get existing correlation ID or generate a new one.
    """
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid


def log_with_correlation(level: str, message: str, **kwargs) -> None:
    """
    Log a message. The RequestIdFilter will automatically attach the ID.
    """
    # cid = get_correlation_id() or 'no-correlation-id' # handled by filter
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, **kwargs)


async def run_with_correlation(coro, correlation_id_value: str | None = None):
    """
    Run an async coroutine with a correlation ID.
    """
    if correlation_id_value is None:
        correlation_id_value = ensure_correlation_id()
    correlation_id.set(correlation_id_value)
    try:
        return await coro
    finally:
        pass


class CorrelationContext:
    """
    Context manager for setting correlation ID in a scope.
    """

    def __init__(self, correlation_id_value: str):
        self.correlation_id_value = correlation_id_value
        self.token = None

    def __enter__(self):
        self.token = correlation_id.set(self.correlation_id_value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            correlation_id.reset(self.token)


async def run_async_with_correlation(
    func, *args, correlation_id_value: str | None = None, **kwargs
):
    """
    Run an async function with correlation ID.
    """
    if correlation_id_value is None:
        correlation_id_value = ensure_correlation_id()
    correlation_id.set(correlation_id_value)
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        log_with_correlation('error', f'Async task failed: {str(e)}', exc_info=True)
        raise


class RequestIdFilter(logging.Filter):
    """
    Log filter that injects the current request/correlation ID into the log record.
    This ensures that all logs, even those without explicit IDs, are tagged.
    """

    def filter(self, record):
        cid = get_correlation_id()
        # Always set request_id to avoid formatting errors
        record.request_id = cid if cid else 'no-request-id'
        
        # We generally rely on the formatter to include the request_id.
        # Prepending it here would cause duplication (e.g. "ID | ID | message").
        return True
