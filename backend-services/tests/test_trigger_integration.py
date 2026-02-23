import pytest
from unittest.mock import AsyncMock, patch
from utils.async_db import db_insert_one, db_delete_one
from utils.database_async import db as async_db
from services.trigger_service import trigger_service
from utils.doorman_cache_util import doorman_cache

@pytest.mark.asyncio
async def test_trigger_management_flow(authed_client):
    # 1. Create a trigger via API
    trigger_data = {
        'collection_name': 'test_trigger_collection',
        'url': 'http://example.com/webhook',
        'event': 'insert',
        'method': 'POST'
    }
    
    # Ensure cache is clean
    doorman_cache.delete_cache('trigger_cache', 'test_trigger_collection')
    
    resp = await authed_client.post('/platform/api-builder/triggers', json=trigger_data)
    assert resp.status_code == 201, resp.text
    # Response model unwraps 'response' dict if not strict mode
    # create_trigger returns {'trigger': doc} in response field
    trigger_id = resp.json().get('trigger', {}).get('_id')
    if not trigger_id:
         # Fallback if strict mode is on or structure is different
         trigger_id = resp.json().get('response', {}).get('trigger', {}).get('_id')
    assert trigger_id
    
    # 2. Verify it's in DB
    triggers_db = await trigger_service.get_triggers_for_collection('test_trigger_collection')
    assert len(triggers_db) == 1
    assert triggers_db[0]['_id'] == trigger_id
    
    # 3. Process matched event
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value.status_code = 200
        
        change_event = {
            'ns': {'db': 'test_db', 'coll': 'test_trigger_collection'},
            'operationType': 'insert',
            'documentKey': {'_id': 'doc1'},
            'fullDocument': {'foo': 'bar'},
            'clusterTime': 12345
        }
        
        await trigger_service.process_event(change_event)
        
        # process_event spawns background tasks, give them time to run
        import asyncio
        await asyncio.sleep(0.1)
        
        # Verify webhook called
        assert mock_request.called
        args, kwargs = mock_request.call_args
        assert args[1] == 'http://example.com/webhook'
        assert kwargs['json']['fullDocument']['foo'] == 'bar'

    # 4. Verify caching (modify DB directly, check logic uses cache)
    # We'll mock db_find_list to fail if called, to prove cache is used.
    with patch('services.trigger_service.db_find_list', side_effect=Exception("Should use cache!")):
        cached_triggers = await trigger_service.get_triggers_for_collection('test_trigger_collection')
        assert len(cached_triggers) == 1
    
    # 5. Delete trigger via API
    del_resp = await authed_client.delete(f'/platform/api-builder/triggers/{trigger_id}')
    assert del_resp.status_code == 200
    
    # 6. Verify cache invalidation (should call DB now, or return empty from DB)
    # Since we deleted it, db_find_list should be called again and return empty
    empty_triggers = await trigger_service.get_triggers_for_collection('test_trigger_collection')
    assert len(empty_triggers) == 0

