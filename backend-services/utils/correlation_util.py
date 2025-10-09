"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from contextvars import ContextVar
from typing import Optional
import uuid
import logging

# Context variable for correlation ID
# This is automatically inherited by async tasks spawned from the same context
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

logger = logging.getLogger('doorman.gateway')


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.

    Returns:
        Current correlation ID or None if not set

    Example:
        >>> cid = get_correlation_id()
        >>> logger.info(f"{cid} | Processing request")
    """
    return correlation_id.get()


def set_correlation_id(value: str) -> None:
    """
    Set the correlation ID in the current context.

    This should be called early in request processing (typically in middleware).
    All async tasks spawned from this context will inherit the same correlation ID.

    Args:
        value: Correlation ID (typically the request ID)

    Example:
        >>> set_correlation_id(request.headers.get('X-Request-ID'))
    """
    correlation_id.set(value)


def ensure_correlation_id() -> str:
    """
    Get existing correlation ID or generate a new one.

    Returns:
        Correlation ID (existing or newly generated)

    Example:
        >>> cid = ensure_correlation_id()
        >>> logger.info(f"{cid} | Background task started")
    """
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id.set(cid)
    return cid


def log_with_correlation(level: str, message: str, **kwargs) -> None:
    """
    Log a message with the correlation ID automatically prepended.

    Args:
        level: Log level (info, warning, error, debug)
        message: Log message
        **kwargs: Additional arguments for logger

    Example:
        >>> log_with_correlation('info', 'Processing payment')
        # Logs: "abc-123 | Processing payment"
    """
    cid = get_correlation_id() or 'no-correlation-id'
    log_message = f"{cid} | {message}"

    log_func = getattr(logger, level.lower(), logger.info)
    log_func(log_message, **kwargs)


async def run_with_correlation(coro, correlation_id_value: Optional[str] = None):
    """
    Run an async coroutine with a correlation ID.

    If correlation_id_value is not provided, uses the current context's correlation ID.

    Args:
        coro: Async coroutine to run
        correlation_id_value: Optional correlation ID to use

    Returns:
        Result of the coroutine

    Example:
        >>> async def background_job():
        ...     log_with_correlation('info', 'Job started')
        ...     await process_data()
        ...
        >>> await run_with_correlation(background_job(), request_id)
    """
    # If no correlation ID provided, use current or generate new
    if correlation_id_value is None:
        correlation_id_value = ensure_correlation_id()

    # Set correlation ID for this task
    correlation_id.set(correlation_id_value)

    try:
        return await coro
    finally:
        # Clear correlation ID after task completes (optional)
        pass


class CorrelationContext:
    """
    Context manager for setting correlation ID in a scope.

    Example:
        >>> with CorrelationContext(request_id):
        ...     log_with_correlation('info', 'Processing request')
        ...     await background_task()
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


async def run_async_with_correlation(func, *args, correlation_id_value: Optional[str] = None, **kwargs):
    """
    Run an async function with correlation ID.

    Args:
        func: Async function to run
        *args: Positional arguments for function
        correlation_id_value: Optional correlation ID
        **kwargs: Keyword arguments for function

    Returns:
        Result of function

    Example:
        >>> await run_async_with_correlation(
        ...     process_payment,
        ...     user_id=123,
        ...     correlation_id_value=request_id
        ... )
    """
    if correlation_id_value is None:
        correlation_id_value = ensure_correlation_id()

    correlation_id.set(correlation_id_value)

    try:
        return await func(*args, **kwargs)
    except Exception as e:
        log_with_correlation('error', f'Async task failed: {str(e)}', exc_info=True)
        raise
