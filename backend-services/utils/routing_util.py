import logging
import os
import platform
import socket
from urllib.parse import urlparse, urlunparse

from utils import api_util
from utils.async_db import db_find_one
from utils.database_async import routing_collection
from utils.doorman_cache_util import doorman_cache

logger = logging.getLogger('doorman.gateway')


_LOCALHOSTS = {'localhost', '127.0.0.1', '::1'}


def _strip_inline_comment(value: str) -> str:
    """Strip inline comments like "value  # comment" without touching URLs."""
    v = (value or '').strip()
    if not v:
        return v
    for i, ch in enumerate(v):
        if ch != '#':
            continue
        if i == 0 or v[i - 1].isspace():
            return v[:i].rstrip()
    return v


def _can_resolve(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False


def _detect_docker() -> bool:
    try:
        if (os.getenv('DOORMAN_IN_DOCKER') or '').strip().lower() in ('1', 'true', 'yes'):
            return True
    except Exception:
        pass
    # Fallback: common Docker marker file
    try:
        return os.path.exists('/.dockerenv')
    except Exception:
        return False


def _resolve_localhost_alias() -> str | None:
    override = (os.getenv('DOORMAN_TEST_HOSTNAME') or os.getenv('DOORMAN_UPSTREAM_HOST') or '').strip()
    if override:
        return override
    if not _detect_docker():
        return None
    # Prefer Docker Desktop DNS name if available
    if _can_resolve('host.docker.internal'):
        return 'host.docker.internal'
    # Linux bridge default
    return os.getenv('DOORMAN_DOCKER_HOST_GATEWAY', '172.17.0.1')


def _normalize_server(server: str | None) -> str | None:
    if server is None:
        return None
    if not isinstance(server, str):
        return server
    server = _strip_inline_comment(server)
    if not server:
        return server
    try:
        parsed = urlparse(server)
    except Exception:
        return server
    host = parsed.hostname
    if not host or host not in _LOCALHOSTS:
        return server
    alias = _resolve_localhost_alias()
    if not alias or alias == host:
        return server

    # Rebuild netloc preserving userinfo and port
    userinfo = ''
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f':{parsed.password}'
        userinfo += '@'
    netloc = f'{userinfo}{alias}'
    if parsed.port:
        netloc += f':{parsed.port}'
    try:
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return server


async def get_client_routing(client_key: str) -> dict | None:
    """Get the routing information for a specific client.

    Args:
        client_key: Client identifier for routing lookup

    Returns:
        Optional[Dict]: Routing document or None if not found
    """
    try:
        client_routing = doorman_cache.get_cache('client_routing_cache', client_key)
        if not client_routing:
            client_routing = await db_find_one(routing_collection, {'client_key': client_key})
            if not client_routing:
                return None
            if client_routing.get('_id'):
                del client_routing['_id']
            doorman_cache.set_cache('client_routing_cache', client_key, client_routing)
        return client_routing
    except Exception as e:
        logger.error(f'Error in get_client_routing: {e}')
        return None


async def get_routing_info(client_key: str) -> str | None:
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
    return _normalize_server(server)


async def pick_upstream_server(
    api: dict, method: str, endpoint_uri: str, client_key: str | None
) -> str | None:
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
            idx_key = endpoint.get('endpoint_id') or f'{api.get("api_id")}:{method}:{endpoint_uri}'
            server_index = doorman_cache.get_cache('endpoint_server_cache', idx_key) or 0
            server = ep_servers[server_index % len(ep_servers)]
            doorman_cache.set_cache(
                'endpoint_server_cache', idx_key, (server_index + 1) % len(ep_servers)
            )
            return _normalize_server(server)

    api_servers = api.get('api_servers') or []
    if isinstance(api_servers, list) and len(api_servers) > 0:
        idx_key = api.get('api_id')
        server_index = doorman_cache.get_cache('endpoint_server_cache', idx_key) or 0
        server = api_servers[server_index % len(api_servers)]
        doorman_cache.set_cache(
            'endpoint_server_cache', idx_key, (server_index + 1) % len(api_servers)
        )
        return _normalize_server(server)

    return None
