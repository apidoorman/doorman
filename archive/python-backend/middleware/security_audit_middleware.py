"""
Security Audit Middleware

Intercepts sensitive requests and logs them to the audit log.
Specifically targets /platform/ routes for modification events.
"""

import logging
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from utils.audit_util import audit

logger = logging.getLogger('doorman.audit')


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for security auditing.
    
    Logs:
    - All modification methods (POST, PUT, DELETE, PATCH)
    - All requests to sensitive paths (/auth, /vault, /platform)
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and audit log sensitive actions.
        """
        # Generate request ID if not present
        request_id = request.headers.get('x-request-id', str(uuid.uuid4()))
        
        # Determine if audit is needed
        should_audit = self._should_audit(request)
        
        start_time = time.time()
        
        # Capture basic info
        method = request.method
        path = request.url.path
        
        # We can't easily read body here without consuming stream (unless we copy it)
        # So we focus on method/path/user/result
        
        response = await call_next(request)
        
        if should_audit:
            try:
                # Extract user if available (from previous middleware)
                actor = self._get_actor(request)
                
                status_code = response.status_code
                duration = (time.time() - start_time) * 1000
                
                details = {
                    'method': method,
                    'path': path,
                    'status_code': status_code,
                    'duration_ms': round(duration, 2),
                    'user_agent': request.headers.get('user-agent'),
                }
                
                # Log audit event
                audit(
                    request=request,
                    request_id=request_id,
                    actor=actor,
                    action=f'{method} {path}',
                    target='platform',
                    status='success' if status_code < 400 else 'failure',
                    details=details
                )
            except Exception as e:
                logger.error(f'Audit logging failed: {e}')
                
        return response

    def _should_audit(self, request: Request) -> bool:
        """Check if request should be audited"""
        method = request.method
        path = request.url.path
        
        # Always audit modifications
        if method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            return True
            
        # Always audit sensitive paths
        if path.startswith('/platform/vault') or \
           path.startswith('/platform/auth') or \
           path.startswith('/platform/tiers'):
            return True
        
        # Audit all platform interactions for stricter security?
        # For now, yes, assume /platform is admin area
        if path.startswith('/platform/'):
            return True
            
        return False

    def _get_actor(self, request: Request) -> str:
        """Extract actor from request state"""
        try:
            # 1. Check jwt_payload from Auth middleware
            if hasattr(request.state, 'jwt_payload') and request.state.jwt_payload:
                return request.state.jwt_payload.get('sub', 'unknown')
                
            # 2. Check user object
            user = getattr(request.state, 'user', None)
            if user:
                if hasattr(user, 'username'):
                    return user.username
                if isinstance(user, dict):
                    return user.get('username') or user.get('sub', 'unknown')
                    
        except Exception:
            pass
            
        return 'anonymous'
