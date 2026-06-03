import logging
import inspect
import pymongo
from fastapi import APIRouter, Request, Response

from models.response_model import ResponseModel
from routes.api_builder_routes import get_builder_collection, get_builder_table_meta
from utils.auth_util import auth_required
from utils.constants import Roles
from utils.role_util import platform_role_required_bool
from utils.response_util import respond_rest

index_router = APIRouter()
logger = logging.getLogger('doorman.gateway')


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


@index_router.get('/tables/{collection_name}/indexes', description='List indexes')
async def list_indexes(collection_name: str, request: Request) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.VIEW_BUILDER_TABLES):
             return respond_rest(ResponseModel(status_code=403, error_code='IDX403', error_message='Permission denied'))

        if not await get_builder_table_meta(collection_name):
             return respond_rest(ResponseModel(status_code=404, error_code='IDX404', error_message='Table not found'))
        
        coll = get_builder_collection(collection_name)
        indexes = []
        cursor = await _maybe_await(coll.list_indexes())
        to_list = getattr(cursor, 'to_list', None)
        if callable(to_list):
            indexes = await _maybe_await(to_list(length=None))
        elif hasattr(cursor, '__aiter__'):
            async for index in cursor:
                indexes.append(index)
        else:
            indexes = list(cursor or [])
            
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

        if not await get_builder_table_meta(collection_name):
             return respond_rest(ResponseModel(status_code=404, error_code='IDX404', error_message='Table not found'))
        
        body = await request.json()
        keys = body.get('keys') # List of [field, direction]
        unique = body.get('unique', False)
        name = body.get('name')
        
        if not keys:
            return respond_rest(ResponseModel(status_code=400, error_code='IDX400', error_message='Missing keys'))

        formatted_keys = []
        for k in keys:
            if not isinstance(k, (list, tuple)) or len(k) != 2:
                return respond_rest(ResponseModel(status_code=400, error_code='IDX400', error_message='Invalid key spec'))
            field = k[0]
            if not field or field == '_id':
                return respond_rest(ResponseModel(status_code=400, error_code='IDX400', error_message='Cannot create indexes on _id here'))
            direction = pymongo.ASCENDING if k[1] == 1 or k[1] == 'asc' else pymongo.DESCENDING
            formatted_keys.append((field, direction))
            
        coll = get_builder_collection(collection_name)
        
        kwargs = {'unique': unique}
        if name:
            if name == '_id_':
                return respond_rest(ResponseModel(status_code=400, error_code='IDX400', error_message='Cannot create _id_ index'))
            kwargs['name'] = name
            
        result = await _maybe_await(coll.create_index(formatted_keys, **kwargs))
        
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

        if not await get_builder_table_meta(collection_name):
             return respond_rest(ResponseModel(status_code=404, error_code='IDX404', error_message='Table not found'))

        if index_name == '_id_':
             return respond_rest(ResponseModel(status_code=400, error_code='IDX400', error_message='Cannot drop _id_ index'))
        
        coll = get_builder_collection(collection_name)
        await _maybe_await(coll.drop_index(index_name))
        
        return respond_rest(ResponseModel(status_code=200, message='Index dropped'))

    except Exception as e:
        logger.error(f'Error dropping index: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='IDX500', error_message=str(e)))
