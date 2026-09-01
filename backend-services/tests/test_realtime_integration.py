import pytest
from unittest.mock import AsyncMock, patch
from services.realtime_service import realtime_service
from fastapi import WebSocket

@pytest.mark.asyncio
async def test_realtime_connection_flow():
    # 1. Mock WebSocket
    mock_ws = AsyncMock(spec=WebSocket)
    collection_name = "test_realtime_coll"
    
    # 2. Connect
    await realtime_service.connect(mock_ws, collection_name)
    assert collection_name in realtime_service.active_connections
    assert mock_ws in realtime_service.active_connections[collection_name]
    
    # 3. Broadcast
    message = {"operation": "insert", "fullDocument": {"foo": "bar"}}
    await realtime_service.broadcast(collection_name, message)
    
    # Verify send_text called
    mock_ws.send_text.assert_called_once()
    args, _ = mock_ws.send_text.call_args
    assert "foo" in args[0]
    
    # 4. Disconnect
    realtime_service.disconnect(mock_ws, collection_name)
    assert collection_name not in realtime_service.active_connections

@pytest.mark.asyncio
async def test_realtime_broadcast_cleanup():
    # Test that failed sends remove the connection
    mock_ws = AsyncMock(spec=WebSocket)
    mock_ws.send_text.side_effect = Exception("Connection closed")
    collection_name = "test_cleanup_coll"
    
    await realtime_service.connect(mock_ws, collection_name)
    await realtime_service.broadcast(collection_name, {"msg": "test"})
    
    assert collection_name not in realtime_service.active_connections
