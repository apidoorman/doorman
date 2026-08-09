"""
Standardized error response utilities
"""

from typing import Any

from models.response_model import ResponseModel
from utils.response_util import process_response


def create_error_response(
    status_code: int,
    error_code: str,
    error_message: str,
    request_id: str | None = None,
    data: dict[str, Any] | None = None,
    api_type: str = 'rest',
) -> dict[str, Any]:
    """
    Create a standardized error response using ResponseModel.
    """
    response_headers = {}
    if request_id:
        response_headers['request_id'] = request_id
    response_model = ResponseModel(
        status_code=status_code,
        response_headers=response_headers,
        error_code=error_code,
        error_message=error_message,
        response=data,
    )
    return process_response(response_model.dict(), api_type)


def success_response(
    status_code: int = 200,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    request_id: str | None = None,
    api_type: str = 'rest',
) -> dict[str, Any]:
    """
    Create a standardized success response using ResponseModel.
    """
    response_headers = {}
    if request_id:
        response_headers['request_id'] = request_id
    response_model = ResponseModel(
        status_code=status_code, response_headers=response_headers, message=message, response=data
    )
    return process_response(response_model.dict(), api_type)
