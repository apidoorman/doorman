"""
Utility functions for API resolution in gateway routes.

Reduces duplicate code for GraphQL/gRPC API name/version parsing.
"""

import re
from typing import Tuple, Optional
from fastapi import Request, HTTPException
from utils.doorman_cache_util import doorman_cache
from utils import api_util


def parse_graphql_grpc_path(path: str, request: Request) -> Tuple[str, str, str]:
    """Parse GraphQL/gRPC path to extract API name and version.

    Args:
        path: Request path (e.g., 'myapi' from '/api/graphql/myapi')
        request: FastAPI Request object (for X-API-Version header)

    Returns:
        Tuple of (api_name, api_version, api_path) where:
        - api_name: Extracted API name from path
        - api_version: Version from X-API-Version header or default 'v1'
        - api_path: Combined path for cache lookup (e.g., 'myapi/v1')

    Raises:
        HTTPException: If X-API-Version header is missing
    """
    # Extract API name from path (last segment)
    api_name = re.sub(r'^.*/', '', path).strip()
    if not api_name:
        raise HTTPException(status_code=400, detail='Invalid API path')

    # Get version from header (required)
    api_version = request.headers.get('X-API-Version')
    if not api_version:
        raise HTTPException(status_code=400, detail='X-API-Version header is required')

    # Build cache lookup path
    api_path = f'{api_name}/{api_version}'

    return api_name, api_version, api_path


async def resolve_api(api_name: str, api_version: str) -> Optional[dict]:
    """Resolve API from cache or database.

    Args:
        api_name: API name
        api_version: API version

    Returns:
        API dict if found, None otherwise
    """
    api_path = f'{api_name}/{api_version}'
    api_key = doorman_cache.get_cache('api_id_cache', api_path)
    return await api_util.get_api(api_key, api_path)


async def resolve_api_from_request(path: str, request: Request) -> Tuple[Optional[dict], str, str, str]:
    """Parse path, extract API name/version, and resolve API in one call.

    Args:
        path: Request path
        request: FastAPI Request object

    Returns:
        Tuple of (api, api_name, api_version, api_path)

    Raises:
        HTTPException: If path is invalid or X-API-Version is missing
    """
    api_name, api_version, api_path = parse_graphql_grpc_path(path, request)
    api = await resolve_api(api_name, api_version)
    return api, api_name, api_version, api_path
