import logging
import uuid
import pymongo
from fastapi import APIRouter, Request, Response

from models.response_model import ResponseModel
from utils.auth_util import auth_required
from utils.constants import Roles
from utils.database_async import db as async_db
from utils.role_util import platform_role_required_bool
from utils.response_util import respond_rest

index_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

def _get_collection(name: str):
    if hasattr(async_db, 'get_collection'):
        return async_db.get_collection(name)
    return getattr(async_db, name)

@index_router.get('/tables/{collection_name}/indexes', description='List indexes')
async def list_indexes(collection_name: str, request: Request) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.VIEW_BUILDER_TABLES):
             return respond_rest(ResponseModel(status_code=403, error_code='IDX403', error_message='Permission denied'))
        
        coll = _get_collection(collection_name)
        indexes = []
        async for index in coll.list_indexes():
            indexes.append(index)
            
        return respond_rest(ResponseModel(status_code=200, response={'indexes': indexes}))
    except Exception as e:
        logger.error(f'Error listing indexes: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='IDX500', error_message=str(e)))

@index_router.post('/tables/{collection_name}/indexes', description='Create index')
async def create_index(collection_name: str, request: Request) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
             return respond_rest(ResponseModel(status_code=403, error_code='IDX403', error_message='Permission denied'))
        
        body = await request.json()
        keys = body.get('keys') # List of [field, direction]
        unique = body.get('unique', False)
        name = body.get('name')
        
        if not keys:
            return respond_rest(ResponseModel(status_code=400, error_code='IDX400', error_message='Missing keys'))

        formatted_keys = []
        for k in keys:
            field = k[0]
            direction = pymongo.ASCENDING if k[1] == 1 or k[1] == 'asc' else pymongo.DESCENDING
            formatted_keys.append((field, direction))
            
        coll = _get_collection(collection_name)
        
        kwargs = {'unique': unique}
        if name:
            kwargs['name'] = name
            
        result = await coll.create_index(formatted_keys, **kwargs)
        
        return respond_rest(ResponseModel(status_code=201, message=f'Index created: {result}'))

    except Exception as e:
        logger.error(f'Error creating index: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='IDX500', error_message=str(e)))

@index_router.delete('/tables/{collection_name}/indexes/{index_name}', description='Drop index')
async def drop_index(collection_name: str, index_name: str, request: Request) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
             return respond_rest(ResponseModel(status_code=403, error_code='IDX403', error_message='Permission denied'))
        
        coll = _get_collection(collection_name)
        await coll.drop_index(index_name)
        
        return respond_rest(ResponseModel(status_code=200, message='Index dropped'))

    except Exception as e:
        logger.error(f'Error dropping index: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='IDX500', error_message=str(e)))
