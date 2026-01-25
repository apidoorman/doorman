"""
GraphQL Utility Functions

Provides:
- Query depth calculation and limiting
- Schema introspection fetching and caching
- GraphQL query validation helpers
"""

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger('doorman.gateway')

# Default maximum query depth
DEFAULT_MAX_DEPTH = 10


def calculate_query_depth(query: str) -> int:
    """
    Calculate the maximum nesting depth of a GraphQL query.
    
    Uses regex-based parsing for performance (no full AST parsing required).
    
    Args:
        query: GraphQL query string
        
    Returns:
        Maximum nesting depth (1 = flat query like "{ users }")
    """
    if not query or not isinstance(query, str):
        return 0
    
    # Remove comments
    query = re.sub(r'#.*$', '', query, flags=re.MULTILINE)
    
    # Remove string literals to avoid counting braces in strings
    query = re.sub(r'"[^"]*"', '""', query)
    query = re.sub(r"'[^']*'", "''", query)
    
    max_depth = 0
    current_depth = 0
    
    for char in query:
        if char == '{':
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == '}':
            current_depth = max(0, current_depth - 1)
    
    return max_depth


def validate_query_depth(query: str, max_depth: int | None = None) -> tuple[bool, str | None]:
    """
    Validate that a query does not exceed maximum depth.
    
    Args:
        query: GraphQL query string
        max_depth: Maximum allowed depth (uses DEFAULT_MAX_DEPTH if None)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if max_depth is None:
        max_depth = DEFAULT_MAX_DEPTH
    
    if max_depth <= 0:
        # Depth limiting disabled
        return True, None
    
    depth = calculate_query_depth(query)
    
    if depth > max_depth:
        return False, f'Query depth {depth} exceeds maximum allowed depth of {max_depth}'
    
    return True, None


def estimate_query_complexity(query: str) -> int:
    """
    Estimate query complexity based on field count.
    
    This is a simple heuristic - counts field-like patterns.
    
    Args:
        query: GraphQL query string
        
    Returns:
        Estimated complexity score
    """
    if not query:
        return 0
    
    # Remove comments and strings
    query = re.sub(r'#.*$', '', query, flags=re.MULTILINE)
    query = re.sub(r'"[^"]*"', '', query)
    
    # Count field names (words before { or after { or before })
    fields = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', query)
    
    # Remove common keywords
    keywords = {'query', 'mutation', 'subscription', 'fragment', 'on', 'true', 'false', 'null'}
    fields = [f for f in fields if f.lower() not in keywords]
    
    return len(fields)


# Standard introspection query
INTROSPECTION_QUERY = '''
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args { name type { name kind } }
        type { name kind ofType { name kind } }
      }
    }
  }
}
'''


async def fetch_introspection_schema(
    url: str,
    headers: dict | None = None,
    timeout: float = 30.0,
) -> dict | None:
    """
    Fetch GraphQL schema via introspection query.
    
    Args:
        url: GraphQL endpoint URL
        headers: Optional headers for authentication
        timeout: Request timeout
        
    Returns:
        Schema dictionary or None if failed
    """
    try:
        request_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if headers:
            request_headers.update(headers)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json={'query': INTROSPECTION_QUERY},
                headers=request_headers,
            )
            
            if response.status_code != 200:
                logger.warning(f'Introspection failed: HTTP {response.status_code}')
                return None
            
            data = response.json()
            
            if 'errors' in data and data['errors']:
                logger.warning(f"Introspection errors: {data['errors']}")
                return None
            
            return data.get('data', {}).get('__schema')
            
    except Exception as e:
        logger.error(f'Error fetching GraphQL schema: {e}')
        return None


def extract_types_from_schema(schema: dict) -> list[dict]:
    """
    Extract type definitions from introspection schema.
    
    Args:
        schema: Introspection schema dictionary
        
    Returns:
        List of type definitions with fields
    """
    if not schema:
        return []
    
    types = []
    for type_def in schema.get('types', []):
        # Skip introspection types
        if type_def.get('name', '').startswith('__'):
            continue
        
        types.append({
            'name': type_def.get('name'),
            'kind': type_def.get('kind'),
            'description': type_def.get('description'),
            'fields': [
                {
                    'name': f.get('name'),
                    'type': f.get('type', {}).get('name') or f.get('type', {}).get('kind'),
                }
                for f in (type_def.get('fields') or [])
            ],
        })
    
    return types


def get_operation_type(schema: dict) -> dict:
    """
    Extract operation types (query, mutation, subscription) from schema.
    
    Args:
        schema: Introspection schema dictionary
        
    Returns:
        Dict with operation type names
    """
    if not schema:
        return {}
    
    return {
        'query': schema.get('queryType', {}).get('name') if schema.get('queryType') else None,
        'mutation': schema.get('mutationType', {}).get('name') if schema.get('mutationType') else None,
        'subscription': schema.get('subscriptionType', {}).get('name') if schema.get('subscriptionType') else None,
    }


def has_subscription_support(schema: dict) -> bool:
    """
    Check if schema supports subscriptions.
    
    Args:
        schema: Introspection schema dictionary
        
    Returns:
        True if subscriptions are supported
    """
    if not schema:
        return False
    
    sub_type = schema.get('subscriptionType')
    return sub_type is not None and sub_type.get('name') is not None


def detect_operation_type(query: str) -> str:
    """
    Detect the operation type from a GraphQL query.
    
    Args:
        query: GraphQL query string
        
    Returns:
        'query', 'mutation', 'subscription', or 'unknown'
    """
    if not query:
        return 'unknown'
    
    # Remove comments
    query = re.sub(r'#.*$', '', query, flags=re.MULTILINE)
    query = query.strip()
    
    # Check for explicit operation type
    if query.startswith('mutation'):
        return 'mutation'
    elif query.startswith('subscription'):
        return 'subscription'
    elif query.startswith('query'):
        return 'query'
    elif query.startswith('{'):
        # Anonymous query
        return 'query'
    
    return 'unknown'


def is_subscription_operation(query: str) -> bool:
    """
    Check if a query is a subscription operation.
    
    Args:
        query: GraphQL query string
        
    Returns:
        True if this is a subscription
    """
    return detect_operation_type(query) == 'subscription'
