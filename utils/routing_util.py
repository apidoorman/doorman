from utils.pygate_cache_util import pygate_cache
from utils.database import routing_collection

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

async def get_client_routing(client_key):
    """
    Get the routing information for a specific client.
    """
    try:
        client_routing = pygate_cache.get_cache('client_routing_cache', client_key)
        if not client_routing:
            client_routing = routing_collection.find_one({'client_key': client_key})
            if not client_routing:
                return None
            if client_routing.get('_id'): del client_routing['_id']
            pygate_cache.set_cache('client_routing_cache', client_key, client_routing)
        return client_routing
    except Exception as e:
        logger.error(f"Error in get_client_routing: {e}")
        return None
    
async def get_routing_info(client_key):
    routing = await get_client_routing(client_key)
    if not routing:
        return None
    server_index = routing.get('server_index', 0)
    api_servers = routing.get('routing_servers', [])
    server = api_servers[server_index]
    server_index = (server_index + 1) % len(api_servers)
    routing['server_index'] = server_index
    pygate_cache.set_cache('client_routing_cache', client_key, routing)
    return server