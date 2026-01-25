"""
Request/Response Transformation Utility

Provides transformation capabilities for API gateway requests and responses.
Supports header, body (JSON), and query parameter transformations.
"""

import copy
import logging
import re
from typing import Any

logger = logging.getLogger('doorman.gateway')


class TransformError(Exception):
    """Raised when a transformation fails."""

    def __init__(self, message: str, path: str | None = None):
        self.message = message
        self.path = path
        super().__init__(self.message)


def _get_jsonpath_value(data: dict, path: str) -> Any:
    """
    Get value from dict using simple JSONPath-like syntax.
    
    Supports:
    - $.field - top-level field
    - $.nested.field - nested field
    - $.array[0] - array index
    
    Args:
        data: Dictionary to extract from
        path: JSONPath-like string (e.g., '$.user.name')
        
    Returns:
        Value at path or None if not found
    """
    if not path or not path.startswith('$.'):
        return None
    
    try:
        parts = path[2:].split('.')  # Remove $. prefix
        current = data
        
        for part in parts:
            if not part:
                continue
                
            # Handle array indexing
            match = re.match(r'^(\w+)\[(\d+)\]$', part)
            if match:
                field, index = match.groups()
                if field:
                    current = current.get(field, [])
                if isinstance(current, list) and int(index) < len(current):
                    current = current[int(index)]
                else:
                    return None
            else:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
                    
            if current is None:
                return None
                
        return current
    except Exception:
        return None


def _set_jsonpath_value(data: dict, path: str, value: Any) -> dict:
    """
    Set value in dict using simple JSONPath-like syntax.
    Creates intermediate dicts/lists as needed.
    
    Args:
        data: Dictionary to modify (modified in-place)
        path: JSONPath-like string (e.g., '$.user.name')
        value: Value to set
        
    Returns:
        Modified dictionary
    """
    if not path or not path.startswith('$.'):
        return data
    
    try:
        parts = path[2:].split('.')
        current = data
        
        for i, part in enumerate(parts[:-1]):
            if not part:
                continue
                
            match = re.match(r'^(\w+)\[(\d+)\]$', part)
            if match:
                field, index = match.groups()
                index = int(index)
                if field:
                    if field not in current:
                        current[field] = []
                    current = current[field]
                while len(current) <= index:
                    current.append({})
                if not isinstance(current[index], dict):
                    current[index] = {}
                current = current[index]
            else:
                if part not in current or not isinstance(current.get(part), dict):
                    current[part] = {}
                current = current[part]
        
        # Set the final value
        final_part = parts[-1]
        if final_part:
            match = re.match(r'^(\w+)\[(\d+)\]$', final_part)
            if match:
                field, index = match.groups()
                index = int(index)
                if field:
                    if field not in current:
                        current[field] = []
                    target = current[field]
                else:
                    target = current
                while len(target) <= index:
                    target.append(None)
                target[index] = value
            else:
                current[final_part] = value
                
        return data
    except Exception as e:
        logger.warning(f'Failed to set JSONPath {path}: {e}')
        return data


def _delete_jsonpath(data: dict, path: str) -> dict:
    """
    Delete value at JSONPath from dict.
    
    Args:
        data: Dictionary to modify (modified in-place)
        path: JSONPath-like string
        
    Returns:
        Modified dictionary
    """
    if not path or not path.startswith('$.'):
        return data
    
    try:
        parts = path[2:].split('.')
        current = data
        
        for part in parts[:-1]:
            if not part:
                continue
            match = re.match(r'^(\w+)\[(\d+)\]$', part)
            if match:
                field, index = match.groups()
                if field:
                    current = current.get(field, [])
                if isinstance(current, list) and int(index) < len(current):
                    current = current[int(index)]
                else:
                    return data
            else:
                current = current.get(part)
                if current is None:
                    return data
        
        final_part = parts[-1]
        if final_part:
            match = re.match(r'^(\w+)\[(\d+)\]$', final_part)
            if match:
                field, index = match.groups()
                index = int(index)
                if field:
                    target = current.get(field, [])
                else:
                    target = current
                if isinstance(target, list) and index < len(target):
                    target.pop(index)
            elif isinstance(current, dict) and final_part in current:
                del current[final_part]
                
        return data
    except Exception:
        return data


def transform_headers(
    headers: dict[str, str],
    transform_config: dict,
    direction: str = 'request'
) -> dict[str, str]:
    """
    Apply header transformations.
    
    Config format:
    {
        "add": {"X-Custom": "value"},
        "remove": ["X-Internal"],
        "rename": {"old-name": "new-name"}
    }
    
    Args:
        headers: Original headers dict
        transform_config: Transformation configuration
        direction: 'request' or 'response'
        
    Returns:
        Transformed headers
    """
    if not transform_config:
        return headers
    
    result = dict(headers)
    config = transform_config.get(direction, transform_config).get('headers', {})
    
    # Remove headers first
    for header_name in config.get('remove', []):
        # Case-insensitive removal
        keys_to_remove = [k for k in result if k.lower() == header_name.lower()]
        for k in keys_to_remove:
            del result[k]
    
    # Rename headers
    for old_name, new_name in config.get('rename', {}).items():
        for k in list(result.keys()):
            if k.lower() == old_name.lower():
                result[new_name] = result.pop(k)
                break
    
    # Add headers (overwrites existing)
    for header_name, header_value in config.get('add', {}).items():
        result[header_name] = str(header_value)
    
    return result


def transform_body(
    body: dict | list | Any,
    transform_config: dict,
    direction: str = 'request'
) -> dict | list | Any:
    """
    Apply body transformations using JSONPath.
    
    Config format:
    {
        "set": {"$.field": "value"},
        "remove": ["$.internal_field"],
        "rename": {"$.old_path": "$.new_path"},
        "wrap": "data"  # Wrap entire body: {"data": <original>}
    }
    
    Args:
        body: Original body (dict, list, or primitive)
        transform_config: Transformation configuration
        direction: 'request' or 'response'
        
    Returns:
        Transformed body
    """
    if not transform_config:
        return body
    
    config = transform_config.get(direction, transform_config).get('body', {})
    
    if not config:
        return body
    
    # Work on a copy
    if isinstance(body, dict):
        result = copy.deepcopy(body)
    elif isinstance(body, list):
        result = copy.deepcopy(body)
    else:
        result = body
    
    # Handle wrap first (wraps entire body in a key)
    wrap_key = config.get('wrap')
    if wrap_key and isinstance(wrap_key, str):
        result = {wrap_key: result}
    
    # Only apply path operations to dicts
    if not isinstance(result, dict):
        return result
    
    # Remove fields
    for path in config.get('remove', []):
        result = _delete_jsonpath(result, path)
    
    # Rename fields (get old value, delete, set new)
    for old_path, new_path in config.get('rename', {}).items():
        value = _get_jsonpath_value(result, old_path)
        if value is not None:
            result = _delete_jsonpath(result, old_path)
            result = _set_jsonpath_value(result, new_path, value)
    
    # Set fields (can add or overwrite)
    for path, value in config.get('set', {}).items():
        result = _set_jsonpath_value(result, path, value)
    
    return result


def transform_query_params(
    params: dict[str, str],
    transform_config: dict,
    direction: str = 'request'
) -> dict[str, str]:
    """
    Apply query parameter transformations.
    
    Config format:
    {
        "add": {"param": "value"},
        "remove": ["debug"],
        "rename": {"old_param": "new_param"}
    }
    
    Args:
        params: Original query parameters
        transform_config: Transformation configuration
        direction: 'request' or 'response'
        
    Returns:
        Transformed query parameters
    """
    if not transform_config:
        return params
    
    result = dict(params)
    config = transform_config.get(direction, transform_config).get('query', {})
    
    # Remove params
    for param_name in config.get('remove', []):
        result.pop(param_name, None)
    
    # Rename params
    for old_name, new_name in config.get('rename', {}).items():
        if old_name in result:
            result[new_name] = result.pop(old_name)
    
    # Add params
    for param_name, param_value in config.get('add', {}).items():
        result[param_name] = str(param_value)
    
    return result


def map_status_code(
    status_code: int,
    transform_config: dict
) -> int:
    """
    Map response status code based on configuration.
    
    Config format (in response section):
    {
        "status_map": {"500": 502, "503": 503}
    }
    
    Args:
        status_code: Original status code
        transform_config: Transformation configuration
        
    Returns:
        Mapped status code
    """
    if not transform_config:
        return status_code
    
    status_map = transform_config.get('response', {}).get('status_map', {})
    
    # Convert to string for lookup (JSON keys are strings)
    str_status = str(status_code)
    if str_status in status_map:
        try:
            return int(status_map[str_status])
        except (ValueError, TypeError):
            pass
    
    return status_code


async def apply_request_transforms(
    headers: dict[str, str],
    body: dict | list | Any,
    query_params: dict[str, str],
    transform_config: dict | None
) -> tuple[dict[str, str], dict | list | Any, dict[str, str]]:
    """
    Apply all request transformations.
    
    Args:
        headers: Request headers
        body: Request body
        query_params: Query parameters
        transform_config: Full transformation config
        
    Returns:
        Tuple of (transformed_headers, transformed_body, transformed_params)
    """
    if not transform_config:
        return headers, body, query_params
    
    try:
        new_headers = transform_headers(headers, transform_config, 'request')
        new_body = transform_body(body, transform_config, 'request')
        new_params = transform_query_params(query_params, transform_config, 'request')
        
        logger.debug('Applied request transformations successfully')
        return new_headers, new_body, new_params
    except Exception as e:
        logger.error(f'Request transformation failed: {e}')
        # Return originals on failure
        return headers, body, query_params


async def apply_response_transforms(
    headers: dict[str, str],
    body: dict | list | Any,
    status_code: int,
    transform_config: dict | None
) -> tuple[dict[str, str], dict | list | Any, int]:
    """
    Apply all response transformations.
    
    Args:
        headers: Response headers
        body: Response body
        status_code: Response status code
        transform_config: Full transformation config
        
    Returns:
        Tuple of (transformed_headers, transformed_body, transformed_status)
    """
    if not transform_config:
        return headers, body, status_code
    
    try:
        new_headers = transform_headers(headers, transform_config, 'response')
        new_body = transform_body(body, transform_config, 'response')
        new_status = map_status_code(status_code, transform_config)
        
        logger.debug('Applied response transformations successfully')
        return new_headers, new_body, new_status
    except Exception as e:
        logger.error(f'Response transformation failed: {e}')
        # Return originals on failure
        return headers, body, status_code


def validate_transform_config(config: dict | None) -> tuple[bool, str | None]:
    """
    Validate transformation configuration structure.
    
    Args:
        config: Configuration to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if config is None:
        return True, None
    
    if not isinstance(config, dict):
        return False, 'Transform config must be a dictionary'
    
    valid_directions = {'request', 'response'}
    valid_sections = {'headers', 'body', 'query', 'status_map'}
    valid_operations = {'add', 'remove', 'rename', 'set', 'wrap'}
    
    for direction in config:
        if direction not in valid_directions:
            return False, f'Invalid direction: {direction}. Must be request or response.'
        
        dir_config = config[direction]
        if not isinstance(dir_config, dict):
            return False, f'{direction} config must be a dictionary'
        
        for section in dir_config:
            if section not in valid_sections:
                return False, f'Invalid section: {section}'
            
            section_config = dir_config[section]
            if section == 'status_map':
                if not isinstance(section_config, dict):
                    return False, 'status_map must be a dictionary'
                continue
            
            if not isinstance(section_config, dict):
                return False, f'{section} config must be a dictionary'
            
            for op in section_config:
                if op not in valid_operations:
                    return False, f'Invalid operation: {op}'
    
    return True, None
