import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger('doorman.gateway')

class GlobalLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Generate or extract Request ID
        from utils.correlation_util import correlation_id
        
        request_id = (
            getattr(request.state, 'request_id', None)
            or correlation_id.get()
            or request.headers.get('X-Request-ID')
            or request.headers.get('request-id')
        )
        if not request_id:
            request_id = str(uuid.uuid4())
        
        correlation_id.set(request_id)
        
        # Store in state if not already present
        if not hasattr(request.state, 'request_id'):
            request.state.request_id = request_id
        
        # 2. Start Timer
        start_time = time.time()
        
        # 3. Log Request Entry (Optional - helpful for incomplete requests)
        # We can default to 'platform' or 'gateway' in type inference if needed.
        # Using a consistent prefix helps.
        # logger.info(f"Request started: {request.method} {request.url.path}")

        try:
            # 4. Process Request
            response = await call_next(request)
            
            # 5. Calculate Duration
            duration = (time.time() - start_time) * 1000
            
            # 6. Log Response
            # Format matches LoggingService extraction regexes:
            # Endpoint: {method} {path}
            # status_code: {code}
            # Total time: {ms}ms
            logger.info(
                f"Endpoint: {request.method} {request.url.path} "
                f"| status_code: {response.status_code} "
                f"| Total time: {duration:.2f}ms"
            )
            
            # Ensure Request ID is returned in headers for debugging
            response.headers['X-Request-ID'] = request_id
            
            return response
            
        except Exception as e:
            # 7. Log Unhandled Exceptions
            duration = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"| Error: {str(e)} | Time: {duration:.2f}ms",
                exc_info=True
            )
            raise
