import pytest


@pytest.mark.asyncio
async def test_routing_endpoint_servers_take_precedence_over_api_servers(authed_client):
    from utils import routing_util
    from utils.database import api_collection
    from utils.doorman_cache_util import doorman_cache

    name, ver = 'route1', 'v1'
    r = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://api1', 'http://api2'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    assert r.status_code in (200, 201)
    r2 = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/echo',
            'endpoint_description': 'echo',
            'endpoint_servers': ['http://ep1', 'http://ep2'],
        },
    )
    assert r2.status_code in (200, 201)

    api = api_collection.find_one({'api_name': name, 'api_version': ver})
    assert api
    api.pop('_id', None)
    doorman_cache.clear_cache('endpoint_server_cache')

    picked = await routing_util.pick_upstream_server(api, 'POST', '/echo', client_key=None)
    assert picked == 'http://ep1'


@pytest.mark.asyncio
async def test_routing_client_specific_routing_over_endpoint_and_api(authed_client):
    from utils import routing_util
    from utils.database import api_collection, routing_collection
    from utils.doorman_cache_util import doorman_cache

    name, ver = 'route2', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://api1', 'http://api2'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/echo',
            'endpoint_description': 'echo',
            'endpoint_servers': ['http://ep1', 'http://ep2'],
        },
    )
    api = api_collection.find_one({'api_name': name, 'api_version': ver})
    api.pop('_id', None)

    routing_collection.insert_one(
        {'client_key': 'ck1', 'routing_servers': ['http://r1', 'http://r2'], 'server_index': 0}
    )
    doorman_cache.clear_cache('client_routing_cache')
    doorman_cache.clear_cache('endpoint_server_cache')

    s1 = await routing_util.pick_upstream_server(api, 'POST', '/echo', client_key='ck1')
    s2 = await routing_util.pick_upstream_server(api, 'POST', '/echo', client_key='ck1')
    assert s1 == 'http://r1'
    assert s2 == 'http://r2'


@pytest.mark.asyncio
async def test_routing_round_robin_api_servers_rotates(authed_client):
    from utils import routing_util
    from utils.database import api_collection
    from utils.doorman_cache_util import doorman_cache

    name, ver = 'route3', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://a1', 'http://a2'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/status',
            'endpoint_description': 'status',
        },
    )
    api = api_collection.find_one({'api_name': name, 'api_version': ver})
    api.pop('_id', None)

    doorman_cache.clear_cache('endpoint_server_cache')
    s1 = await routing_util.pick_upstream_server(api, 'GET', '/status', client_key=None)
    s2 = await routing_util.pick_upstream_server(api, 'GET', '/status', client_key=None)
    s3 = await routing_util.pick_upstream_server(api, 'GET', '/status', client_key=None)
    assert [s1, s2, s3] == ['http://a1', 'http://a2', 'http://a1']


@pytest.mark.asyncio
async def test_routing_round_robin_endpoint_servers_rotates(authed_client):
    from utils import routing_util
    from utils.database import api_collection
    from utils.doorman_cache_util import doorman_cache

    name, ver = 'route4', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://a1', 'http://a2'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/echo',
            'endpoint_description': 'echo',
            'endpoint_servers': ['http://e1', 'http://e2'],
        },
    )
    api = api_collection.find_one({'api_name': name, 'api_version': ver})
    api.pop('_id', None)

    doorman_cache.clear_cache('endpoint_server_cache')
    s1 = await routing_util.pick_upstream_server(api, 'POST', '/echo', client_key=None)
    s2 = await routing_util.pick_upstream_server(api, 'POST', '/echo', client_key=None)
    s3 = await routing_util.pick_upstream_server(api, 'POST', '/echo', client_key=None)
    assert [s1, s2, s3] == ['http://e1', 'http://e2', 'http://e1']


@pytest.mark.asyncio
async def test_routing_round_robin_index_persists_in_cache(authed_client):
    from utils import routing_util
    from utils.database import api_collection
    from utils.doorman_cache_util import doorman_cache

    name, ver = 'route5', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': f'{name} {ver}',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://a1', 'http://a2', 'http://a3'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/status',
            'endpoint_description': 'status',
        },
    )
    api = api_collection.find_one({'api_name': name, 'api_version': ver})
    api.pop('_id', None)

    doorman_cache.clear_cache('endpoint_server_cache')
    await routing_util.pick_upstream_server(api, 'GET', '/status', client_key=None)
    await routing_util.pick_upstream_server(api, 'GET', '/status', client_key=None)
    idx = doorman_cache.get_cache('endpoint_server_cache', api['api_id'])
    assert idx == 2

    s3 = await routing_util.pick_upstream_server(api, 'GET', '/status', client_key=None)
    assert s3 == 'http://a3'
    idx_after = doorman_cache.get_cache('endpoint_server_cache', api['api_id'])
    assert idx_after == 0
