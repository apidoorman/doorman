"""
Analytics middleware for capturing request/response metrics.

Automatically records detailed metrics for every request passing through
the gateway, including per-endpoint tracking and full performance data.
"""

import logging
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from utils.enhanced_metrics_util import enhanced_metrics_store
from utils.metrics_util import metrics_store

logger = logging.getLogger('doorman.analytics')


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture comprehensive request/response metrics.

    Records:
    - Response time
    - Status code
    - User (from auth)
    - API name and version
    - Endpoint URI and method
    - Request/response sizes
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and record metrics.
        """
        # Start timing
        start_time = time.time()

        # Extract request metadata
        method = request.method
        path = str(request.url.path)

        # Estimate request size (headers + body)
        request_size = 0
        try:
            # Headers size
            request_size += sum(len(k) + len(v) for k, v in request.headers.items())
            # Body size (if available)
            if 'content-length' in request.headers:
                request_size += int(request.headers['content-length'])
        except Exception:
            pass

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Extract response metadata
        status_code = response.status_code

        # Estimate response size
        response_size = 0
        try:
            # Headers size
            response_size += sum(len(k) + len(v) for k, v in response.headers.items())
            # Body size (if available)
            if 'content-length' in response.headers:
                response_size += int(response.headers['content-length'])
        except Exception:
            pass

        # Extract user from request state (set by auth middleware)
        username = None
        try:
            if hasattr(request.state, 'user'):
                username = (
                    request.state.user.get('sub') if isinstance(request.state.user, dict) else None
                )
        except Exception:
            pass

        # Parse API and endpoint from path
        api_key, endpoint_uri = self._parse_api_endpoint(path)

        # Record metrics only for API traffic; exclude platform endpoints
        try:
            if path.startswith('/api/'):
                enhanced_metrics_store.record(
                    status=status_code,
                    duration_ms=duration_ms,
                    username=username,
                    api_key=api_key,
                    endpoint_uri=endpoint_uri,
                    method=method,
                    bytes_in=request_size,
                    bytes_out=response_size,
                )
                # Maintain legacy monitor metrics (used by /platform/monitor/metrics)
                metrics_store.record(
                    status=status_code,
                    duration_ms=duration_ms,
                    username=username,
                    api_key=api_key,
                    bytes_in=request_size,
                    bytes_out=response_size,
                )
        except Exception as e:
            logger.error(f'Failed to record analytics: {str(e)}')

        return response

    def _parse_api_endpoint(self, path: str) -> tuple[str | None, str | None]:
        """
        Parse API key and endpoint URI from request path.

        Examples:
        - /api/rest/customer/v1/users -> ("rest:customer", "/customer/v1/users")
        - /platform/analytics/overview -> (None, "/platform/analytics/overview")
        """
        try:
            # Check if it's an API request
            if path.startswith('/api/rest/'):
                # REST API: /api/rest/{api_name}/{version}/{endpoint}
                parts = path.split('/')
                if len(parts) >= 5:
                    api_name = parts[3]
                    parts[4]
                    endpoint_uri = '/' + '/'.join(parts[3:])
                    return f'rest:{api_name}', endpoint_uri

            elif path.startswith('/api/graphql/'):
                # GraphQL API
                parts = path.split('/')
                if len(parts) >= 4:
                    api_name = parts[3]
                    return f'graphql:{api_name}', path

            elif path.startswith('/api/soap/'):
                # SOAP API
                parts = path.split('/')
                if len(parts) >= 4:
                    api_name = parts[3]
                    return f'soap:{api_name}', path

            elif path.startswith('/api/grpc/'):
                # gRPC API
                parts = path.split('/')
                if len(parts) >= 4:
                    api_name = parts[3]
                    return f'grpc:{api_name}', path

            # Platform endpoints (not API requests)
            return None, path

        except Exception:
            return None, path


def setup_analytics_middleware(app):
    """
    Add analytics middleware to FastAPI app.

    Should be called during app initialization.
    """
    app.add_middleware(AnalyticsMiddleware)
    logger.info('Analytics middleware initialized')
