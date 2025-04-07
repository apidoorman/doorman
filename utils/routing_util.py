from services.cache import pygate_cache
from utils.database import db

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

routing_collection = db.routings

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