import logging
import httpx
import json
from utils.doorman_cache_util import doorman_cache
from utils.async_db import db_find_list, db_insert_one, db_delete_one
from utils.database_async import db as async_db

logger = logging.getLogger('doorman.triggers')
TRIGGER_COLLECTION = 'api_triggers'

class TriggerService:
    def _get_registry(self):
        if hasattr(async_db, 'get_collection'):
            return async_db.get_collection(TRIGGER_COLLECTION)
        return getattr(async_db, TRIGGER_COLLECTION)

    async def get_triggers_for_collection(self, collection_name: str) -> list[dict]:
        """Get all triggers for a collection, using cache."""
        cached = doorman_cache.get_cache('trigger_cache', collection_name)
        if cached is not None:
             return cached
             
        query = {'collection_name': collection_name}
        triggers = await db_find_list(self._get_registry(), query)
        
        # Serialize ObjectId for cache
        for t in triggers:
            if '_id' in t:
                t['_id'] = str(t['_id'])
                
        doorman_cache.set_cache('trigger_cache', collection_name, triggers)
        return triggers

    async def create_trigger(self, trigger_doc: dict) -> dict | None:
        """Create a trigger and invalidate cache."""
        res = await db_insert_one(self._get_registry(), trigger_doc)
        if res and res.inserted_id:
            trigger_doc['_id'] = str(res.inserted_id)
            # Invalidate cache
            doorman_cache.delete_cache('trigger_cache', trigger_doc['collection_name'])
            return trigger_doc
        return None

    async def delete_trigger(self, trigger_id: str) -> bool:
        """Delete a trigger and invalidate cache."""
        # Need to find it first to know which collection to invalidate
        # Or just invalidate all? No, finding is better.
        # But wait, if we delete by ID, we don't know the collection name unless we lookup.
        # However, for efficiency, maybe just invalidate if we can.
        # Let's do a lookup.
        from utils.async_db import db_find_one
        existing = await db_find_one(self._get_registry(), {'_id': trigger_id})
        
        res = await db_delete_one(self._get_registry(), {'_id': trigger_id})
        if res and res.deleted_count > 0:
            if existing and 'collection_name' in existing:
                doorman_cache.delete_cache('trigger_cache', existing['collection_name'])
            return True
        return False

    async def process_event(self, change: dict):
        """
        Process a MongoDB change stream event and execute matching triggers.
        """
        try:
            ns = change.get('ns') or {}
            db = ns.get('db')
            coll = ns.get('coll')
            
            if not coll:
                return

            op_type = change.get('operationType')
            # insert, update, replace, delete
            
            # Get triggers from cache/db
            triggers = await self.get_triggers_for_collection(coll)
            
            if not triggers:
                return

            # Filter in memory for matching event type
            matching_triggers = [
                t for t in triggers 
                if t.get('event') == '*' or t.get('event') == op_type
            ]

            if not matching_triggers:
                return

            # Execute triggers
            import asyncio
            for trigger in matching_triggers:
                asyncio.create_task(self._execute_trigger(trigger, change))

        except Exception as e:
            logger.error(f"Error processing trigger event: {e}")

    async def _execute_trigger(self, trigger: dict, change: dict):
        url = trigger.get('url')
        method = trigger.get('method', 'POST')
        headers = trigger.get('headers') or {}
        
        if not url:
            return

        try:
            # Prepare payload
            payload = {
                'event': change.get('operationType'),
                'collection': change.get('ns', {}).get('coll'),
                'documentKey': change.get('documentKey'),
                'fullDocument': change.get('fullDocument'),
                'updateDescription': change.get('updateDescription'),
                'timestamp': str(change.get('clusterTime')), # simplified
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, url, json=payload, headers=headers)
                if response.status_code >= 400:
                    logger.warning(f"Trigger {trigger.get('_id')} failed: {response.status_code} {response.text}")
                else:
                    logger.info(f"Trigger {trigger.get('_id')} executed successfully for {url}")
        except Exception as e:
            logger.error(f"Trigger execution failed for {url}: {e}")

trigger_service = TriggerService()
