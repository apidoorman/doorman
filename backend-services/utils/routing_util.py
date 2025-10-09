# External imports
from typing import Optional, Dict
import logging

# Internal imports
from utils.doorman_cache_util import doorman_cache
from utils.database import routing_collection
from utils import api_util

logger = logging.getLogger('doorman.gateway')

async def get_client_routing(client_key: str) -> Optional[Dict]:
    """Get the routing information for a specific client.

    Args:
        client_key: Client identifier for routing lookup

    Returns:
        Optional[Dict]: Routing document or None if not found
    """
    try:
        client_routing = doorman_cache.get_cache('client_routing_cache', client_key)
        if not client_routing:
            client_routing = routing_collection.find_one({'client_key': client_key})
            if not client_routing:
                return None
            if client_routing.get('_id'): del client_routing['_id']
            doorman_cache.set_cache('client_routing_cache', client_key, client_routing)
        return client_routing
    except Exception as e:
        logger.error(f'Error in get_client_routing: {e}')
        return None

async def get_routing_info(client_key: str) -> Optional[str]:
    """Get next upstream server for client using round-robin.

    Args:
        client_key: Client identifier for routing lookup

    Returns:
        Optional[str]: Upstream server URL or None if no routing found
    """
    routing = await get_client_routing(client_key)
    if not routing:
        return None
    server_index = routing.get('server_index', 0)
    api_servers = routing.get('routing_servers', [])
    server = api_servers[server_index]
    server_index = (server_index + 1) % len(api_servers)
    routing['server_index'] = server_index
    doorman_cache.set_cache('client_routing_cache', client_key, routing)
    return server

async def pick_upstream_server(api: Dict, method: str, endpoint_uri: str, client_key: Optional[str]) -> Optional[str]:
    """Resolve upstream server with precedence: Routing (1) > Endpoint (2) > API (3).

    - Routing: client-specific routing list with round-robin in the routing doc/cache.
    - Endpoint: endpoint_servers list on the endpoint doc, round-robin via cache key endpoint_id.
    - API: api_servers list on the API doc, round-robin via cache key api_id.
    """

    if client_key:
        server = await get_routing_info(client_key)
        if server:
            return server

    try:
        endpoint = await api_util.get_endpoint(api, method, endpoint_uri)
    except Exception:
        endpoint = None
    if endpoint:
        ep_servers = endpoint.get('endpoint_servers') or []
        if isinstance(ep_servers, list) and len(ep_servers) > 0:
            idx_key = endpoint.get('endpoint_id') or f"{api.get('api_id')}:{method}:{endpoint_uri}"
            server_index = doorman_cache.get_cache('endpoint_server_cache', idx_key) or 0
            server = ep_servers[server_index % len(ep_servers)]
            doorman_cache.set_cache('endpoint_server_cache', idx_key, (server_index + 1) % len(ep_servers))
            return server

    api_servers = api.get('api_servers') or []
    if isinstance(api_servers, list) and len(api_servers) > 0:
        idx_key = api.get('api_id')
        server_index = doorman_cache.get_cache('endpoint_server_cache', idx_key) or 0
        server = api_servers[server_index % len(api_servers)]
        doorman_cache.set_cache('endpoint_server_cache', idx_key, (server_index + 1) % len(api_servers))
        return server

    return None
