"""
Standardized error response utilities

This module provides helpers for creating consistent error responses across all routes.
All errors should use ResponseModel with proper error codes from utils.error_codes.

Usage:
    from utils.error_util import create_error_response
    from utils.error_codes import ErrorCode

    # In a route handler
    return create_error_response(
        status_code=404,
        error_code=ErrorCode.USER_NOT_FOUND,
        error_message="User with ID 123 not found",
        request_id=request_id
    )
"""

from models.response_model import ResponseModel
from utils.response_util import process_response
from typing import Optional, Dict, Any


def create_error_response(
    status_code: int,
    error_code: str,
    error_message: str,
    request_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    api_type: str = 'rest'
) -> Dict[str, Any]:
    """
    Create a standardized error response using ResponseModel.

    All error responses should use this function to ensure consistency.

    Args:
        status_code: HTTP status code (400, 401, 403, 404, 500, etc.)
        error_code: Error code from ErrorCode class (e.g., ErrorCode.USER_NOT_FOUND)
        error_message: Human-readable error message
        request_id: Optional request ID for tracing
        data: Optional additional data to include in response
        api_type: API type for response processing (default: 'rest')

    Returns:
        Processed response dict ready to return from route handler

    Example:
        >>> from utils.error_codes import ErrorCode
        >>> response = create_error_response(
        ...     status_code=404,
        ...     error_code=ErrorCode.USER_NOT_FOUND,
        ...     error_message="User not found",
        ...     request_id="abc-123"
        ... )
        >>> # Returns: ResponseModel with consistent structure
    """
    response_headers = {}
    if request_id:
        response_headers['request_id'] = request_id

    response_model = ResponseModel(
        status_code=status_code,
        response_headers=response_headers,
        error_code=error_code,
        error_message=error_message,
        response=data
    )

    return process_response(response_model.dict(), api_type)


def success_response(
    status_code: int = 200,
    message: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    api_type: str = 'rest'
) -> Dict[str, Any]:
    """
    Create a standardized success response using ResponseModel.

    Args:
        status_code: HTTP status code (default: 200)
        message: Optional success message
        data: Response data
        request_id: Optional request ID for tracing
        api_type: API type for response processing (default: 'rest')

    Returns:
        Processed response dict ready to return from route handler

    Example:
        >>> response = success_response(
        ...     status_code=201,
        ...     message="User created successfully",
        ...     data={"user_id": "123"},
        ...     request_id="abc-123"
        ... )
    """
    response_headers = {}
    if request_id:
        response_headers['request_id'] = request_id

    response_model = ResponseModel(
        status_code=status_code,
        response_headers=response_headers,
        message=message,
        response=data
    )

    return process_response(response_model.dict(), api_type)
