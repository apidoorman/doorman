"""
Subscription Manager for Real-time Updates via WebSockets.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

from utils.database_async import async_database
from services.trigger_service import trigger_service

logger = logging.getLogger('doorman.gateway')


class RealtimeService:
    """Manages WebSocket connections and broadcasts database change events."""

    def __init__(self):
        # Map: collection_name -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._running = False
        self._listener_task = None

    async def connect(self, websocket: WebSocket, collection_name: str):
        """Accept connection and register client for a specific collection."""
        await websocket.accept()
        if collection_name not in self.active_connections:
            self.active_connections[collection_name] = set()
        self.active_connections[collection_name].add(websocket)
        logger.debug(f"Client connected to stream: {collection_name}")

    def disconnect(self, websocket: WebSocket, collection_name: str):
        """Remove client connection."""
        if collection_name in self.active_connections:
            self.active_connections[collection_name].discard(websocket)
            if not self.active_connections[collection_name]:
                del self.active_connections[collection_name]
        logger.debug(f"Client disconnected from stream: {collection_name}")

    async def broadcast(self, collection_name: str, message: dict):
        """Send message to all clients subscribed to the collection."""
        if collection_name not in self.active_connections:
            return

        connections = self.active_connections[collection_name]
        to_remove = set()

        # Convert message to JSON string once
        # Use default=str to handle ObjectIds and datetimes if needed, though
        # ideally the caller should prepare a JSON-safe dict.
        json_msg = json.dumps(message, default=str)

        for connection in connections:
            try:
                await connection.send_text(json_msg)
            except Exception:
                to_remove.add(connection)

        for closed_connection in to_remove:
            self.disconnect(closed_connection, collection_name)

    async def start_listener(self):
        """Start background task to listen for MongoDB change streams."""
        if self._running:
            return
        self._running = True
        self._listener_task = asyncio.create_task(self._watch_changes())
        logger.info("Started MongoDB Change Stream Listener")

    async def stop_listener(self):
        """Stop background listener."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped MongoDB Change Stream Listener")

    async def _watch_changes(self):
        """Watch entire database for changes and route to subscribers."""
        if async_database.memory_only:
             logger.warning("Change streams not supported in Memory-only mode.")
             return

        try:
            # Watch the entire database (requires admin privileges or specialized setup)
            # Alternatively, we iterate through known collections or handle dynamically.
            # Watching db.watch() captures all collection events.
            # However, PyMongo 3.6+ supports db.watch().
            # Note: change stream requires replica set.
            async with async_database.db.watch(full_document='updateLookup') as stream:
                async for change in stream:
                    if not self._running:
                        break
                    
                    # Dispatch to triggers
                    await trigger_service.process_event(change)
                    

                    
                    # Dispatch to subscriptions

                    # 'ns' contains 'db' and 'coll'
                    namespace = change.get('ns')
                    if not namespace:
                        continue
                    
                    collection_name = namespace.get('coll')
                    if not collection_name or collection_name not in self.active_connections:
                        continue

                    operation_type = change.get('operationType')
                    
                    # Prepare the payload
                    payload = {
                        'operation': operation_type,
                        'documentKey': change.get('documentKey'),
                        # 'fullDocument' is present for 'insert', 'replace', 'update' (if configured)
                        'fullDocument': change.get('fullDocument'),
                        # 'updateDescription' for updates
                        'updateDescription': change.get('updateDescription'),
                    }

                    await self.broadcast(collection_name, payload)

        except Exception as e:
            logger.error(f"Error in Change Stream Listener: {e}")
            self._running = False
            # Simple retry logic could be added here
            await asyncio.sleep(5)
            if self._running:
                asyncio.create_task(self._watch_changes())


# Global instance
realtime_service = RealtimeService()
