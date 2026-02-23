import csv
import io
import json
import logging
import uuid
import time
from typing import Any, List

from fastapi import APIRouter, Request, Response, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse

from models.response_model import ResponseModel
from utils.async_db import (
    db_delete_one,
    db_find_list,
    db_insert_one,
    db_find_one,
    db_insert_many
)
from utils.auth_util import auth_required
from utils.constants import Headers, Messages, Roles
from utils.database_async import db as async_db
from utils.role_util import platform_role_required_bool
from utils.response_util import respond_rest

import_export_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

TABLE_REGISTRY_COLLECTION = 'api_builder_tables'

def _get_collection(name: str):
    if hasattr(async_db, 'get_collection'):
        return async_db.get_collection(name)
    return getattr(async_db, name)

@import_export_router.get('/tables/{collection_name}/export', description='Export table data')
async def export_table(collection_name: str, request: Request, format: str = Query('json', regex='^(json|csv)$')) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        # Check permissions (Builder access)
        if not await platform_role_required_bool(username, Roles.VIEW_BUILDER_TABLES):
             return respond_rest(ResponseModel(status_code=403, error_code='EXP403', error_message='Permission denied'))
        
        # Get data
        coll = _get_collection(collection_name)
        items = await db_find_list(coll, {})
        
        # Safe JSON serialization
        for item in items:
            if '_id' in item: item['_id'] = str(item['_id'])

        if format == 'json':
            content = json.dumps(items, indent=2, default=str)
            return Response(content=content, media_type='application/json', headers={
                'Content-Disposition': f'attachment; filename="{collection_name}.json"'
            })
        
        elif format == 'csv':
            if not items:
                return Response(content='', media_type='text/csv')
            
            output = io.StringIO()
            # Determine headers from all keys in all items
            keys = set()
            for item in items:
                keys.update(item.keys())
            
            writer = csv.DictWriter(output, fieldnames=sorted(list(keys)))
            writer.writeheader()
            for item in items:
                # Flat serialization for CSV? 
                # Complex objects might be stringified.
                row = {}
                for k in keys:
                    val = item.get(k)
                    if isinstance(val, (dict, list)):
                        row[k] = json.dumps(val)
                    else:
                        row[k] = val
                writer.writerow(row)
            
            return Response(content=output.getvalue(), media_type='text/csv', headers={
                'Content-Disposition': f'attachment; filename="{collection_name}.csv"'
            })

    except Exception as e:
        logger.error(f'Error exporting table: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='EXP500', error_message=str(e)))

@import_export_router.post('/tables/{collection_name}/import', description='Import table data')
async def import_table(
    collection_name: str, 
    request: Request, 
    file: UploadFile = File(...)
) -> Response:
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS): # stricter for import
             return respond_rest(ResponseModel(status_code=403, error_code='IMP403', error_message='Permission denied'))

        content = await file.read()
        items = []

        if file.filename.endswith('.json'):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                     items = [data]
            except json.JSONDecodeError:
                return respond_rest(ResponseModel(status_code=400, error_code='IMP400', error_message='Invalid JSON'))

        elif file.filename.endswith('.csv'):
            try:
                # Decode bytes to string
                text = content.decode('utf-8')
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    # Attempt to parse JSON fields if they look like JSON?
                    # For simplicity, we keep them as strings or try basic int conversion
                    clean_row = {}
                    for k, v in row.items():
                        if v and (v.startswith('{') or v.startswith('[')):
                            try:
                                clean_row[k] = json.loads(v)
                            except:
                                clean_row[k] = v
                        else:
                            # Try number
                            try:
                                if '.' in v:
                                    clean_row[k] = float(v)
                                else:
                                    clean_row[k] = int(v)
                            except:
                                clean_row[k] = v
                    items.append(clean_row)
            except Exception as e:
                return respond_rest(ResponseModel(status_code=400, error_code='IMP400', error_message=f'Invalid CSV: {e}'))

        else:
             return respond_rest(ResponseModel(status_code=400, error_code='IMP400', error_message='Unsupported file type'))

        if not items:
             return respond_rest(ResponseModel(status_code=400, error_code='IMP400', error_message='No items found in file'))

        # Insert items
        coll = _get_collection(collection_name)
        # Remove _id if it exists to avoid collision? Or keep it?
        # If _id exists, db_insert might fail with DuplicateKey.
        # We'll use insert, and if _id is present, we try. If it fails, report error?
        # Or remove _id and generate new one always?
        # Use case: Backup/Restore -> Keep _id. Use insert_many with ordered=False to skip duplicates?
        
        # Let's clean _id if it's not a valid ObjectId format or just let Mongo handle it.
        # But if importing from JSON export, _id is string. Mongo uses ObjectId.
        # We should convert _id to ObjectId if possible, or remove it.
        # For simplicity, let's remove _id and treat it as new data, UNLESS simple restore.
        # User might want to update existing... import implies 'add'.
        
        # We will strip _id to be safe and avoid conflicts.
        for item in items:
            if '_id' in item:
                del item['_id']
        
        await db_insert_many(coll, items)
        
        return respond_rest(ResponseModel(status_code=200, message=f'Successfully imported {len(items)} items'))

    except Exception as e:
        logger.error(f'Error importing table: {e}', exc_info=True)
        return respond_rest(ResponseModel(status_code=500, error_code='IMP500', error_message=str(e)))
