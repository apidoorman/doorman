import uuid

import pytest

from models.create_group_model import CreateGroupModel
from models.create_role_model import CreateRoleModel
from models.create_routing_model import CreateRoutingModel
from services.group_service import GroupService
from services.role_service import RoleService
from services.routing_service import RoutingService
from utils.database import group_collection, routing_collection
from utils.database_async import role_collection
from utils.doorman_cache_util import doorman_cache


@pytest.mark.asyncio
async def test_group_create_rejects_duplicate_after_cache_clear():
    group_name = f'grp-{uuid.uuid4().hex}'
    group_collection.insert_one({'group_name': group_name})
    doorman_cache.clear_cache('group_cache')

    response = await GroupService.create_group(CreateGroupModel(group_name=group_name), 'req-group')

    assert response['status_code'] == 400
    assert response['error_code'] == 'GRP001'


@pytest.mark.asyncio
async def test_role_create_rejects_duplicate_after_cache_clear():
    role_name = f'role-{uuid.uuid4().hex}'
    await role_collection.insert_one({'role_name': role_name})
    doorman_cache.clear_cache('role_cache')

    response = await RoleService.create_role(
        CreateRoleModel(role_name=role_name, role_description='duplicate test role'),
        'req-role',
    )

    assert response['status_code'] == 400
    assert response['error_code'] == 'ROLE001'


@pytest.mark.asyncio
async def test_routing_create_rejects_duplicate_after_cache_clear():
    client_key = f'client-{uuid.uuid4().hex}'
    routing_collection.insert_one(
        {
            'routing_name': f'route-{uuid.uuid4().hex}',
            'routing_servers': ['http://example.com'],
            'client_key': client_key,
            'server_index': 0,
        }
    )
    doorman_cache.clear_cache('client_routing_cache')

    response = await RoutingService.create_routing(
        CreateRoutingModel(
            routing_name=f'route-{uuid.uuid4().hex}',
            routing_servers=['http://example.com'],
            client_key=client_key,
        ),
        'req-routing',
    )

    assert response['status_code'] == 400
    assert response['error_code'] == 'RTG001'
