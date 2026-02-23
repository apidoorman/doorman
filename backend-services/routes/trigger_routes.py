import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response

from models.response_model import ResponseModel
from utils.async_db import (
    db_delete_one,
    db_find_list,
    db_insert_one,
)
from utils.auth_util import auth_required
from utils.constants import Headers, Messages, Roles
from utils.database_async import db as async_db
from utils.role_util import platform_role_required_bool
from utils.response_util import respond_rest

trigger_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

TRIGGER_COLLECTION = 'api_triggers'

def _get_collection():
    if hasattr(async_db, 'get_collection'):
        return async_db.get_collection(TRIGGER_COLLECTION)
    return getattr(async_db, TRIGGER_COLLECTION)

@trigger_router.get('/triggers', description='List triggers')
async def list_triggers(request: Request) -> Response:
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
             return respond_rest(ResponseModel(status_code=403, error_code='TRG403', error_message='Permission denied'))
        
        collection_name = request.query_params.get('collection_name')
        query = {}
        if collection_name:
            query['collection_name'] = collection_name
            
        triggers = await db_find_list(_get_collection(), query)
        for t in triggers:
            if '_id' in t: t['_id'] = str(t['_id'])
            
        return respond_rest(ResponseModel(status_code=200, response={'triggers': triggers}))
    except Exception as e:
        logger.error(f'Error listing triggers: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='TRG500', error_message=str(e)))

from services.trigger_service import trigger_service

@trigger_router.post('/triggers', description='Create trigger')
async def create_trigger(request: Request) -> Response:
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
             return respond_rest(ResponseModel(status_code=403, error_code='TRG403', error_message='Permission denied'))
        
        body = await request.json()
        collection_name = body.get('collection_name')
        url = body.get('url')
        event = body.get('event') # insert, update, replace, delete, or *
        
        if not collection_name or not url or not event:
            return respond_rest(ResponseModel(status_code=400, error_code='TRG400', error_message='Missing required fields'))

        doc = {
            'collection_name': collection_name,
            'url': url,
            'event': event,
            'method': body.get('method', 'POST'),
            'headers': body.get('headers') or {},
            'created_at': int(time.time() * 1000),
            'created_by': username
        }
        
        created = await trigger_service.create_trigger(doc)
        if created:
            return respond_rest(ResponseModel(status_code=201, response={'trigger': created}))
            
        return respond_rest(ResponseModel(status_code=500, error_code='TRG500', error_message='Failed to create trigger'))
    except Exception as e:
        logger.error(f'Error creating trigger: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='TRG500', error_message=str(e)))

@trigger_router.delete('/triggers/{trigger_id}', description='Delete trigger')
async def delete_trigger(trigger_id: str, request: Request) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
             return respond_rest(ResponseModel(status_code=403, error_code='TRG403', error_message='Permission denied'))
             
        success = await trigger_service.delete_trigger(trigger_id)
        if success:
            return respond_rest(ResponseModel(status_code=200, message='Trigger deleted'))
            
        return respond_rest(ResponseModel(status_code=404, error_code='TRG404', error_message='Trigger not found'))
    except Exception as e:
        logger.error(f'Error deleting trigger: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='TRG500', error_message=str(e)))
