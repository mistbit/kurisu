"""Tests for WebSocket functionality."""
import json
import pytest
from unittest.mock import AsyncMock

from app.api.v1.websocket import ConnectionManager


@pytest.mark.asyncio
async def test_connection_manager_connect():
    """Test WebSocket connection manager connect functionality."""
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    await manager.connect(mock_ws, market_id=1, timeframe="1h")

    # Verify connection was accepted
    mock_ws.accept.assert_called_once()

    # Verify subscription was registered
    assert manager.get_subscribers(1, "1h") == 1

    # Verify stats
    stats = manager.get_stats()
    assert stats["active_connections"] == 1
    assert stats["total_connections_served"] == 1


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    """Test WebSocket connection manager disconnect functionality."""
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    # Connect first
    await manager.connect(mock_ws, market_id=1, timeframe="1h")
    assert manager.get_subscribers(1, "1h") == 1

    # Then disconnect
    await manager.disconnect(mock_ws)

    # Verify subscription was removed
    assert manager.get_subscribers(1, "1h") == 0

    # Verify stats
    stats = manager.get_stats()
    assert stats["active_connections"] == 0


@pytest.mark.asyncio
async def test_connection_manager_broadcast():
    """Test broadcasting messages to subscribers."""
    manager = ConnectionManager()

    # Create multiple mock connections
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws2.accept = AsyncMock()
    mock_ws1.send_text = AsyncMock()
    mock_ws2.send_text = AsyncMock()

    # Connect both to same subscription
    await manager.connect(mock_ws1, market_id=1, timeframe="1h")
    await manager.connect(mock_ws2, market_id=1, timeframe="1h")

    # Broadcast a message
    data = {
        "type": "ohlcv_update",
        "market_id": 1,
        "timeframe": "1h",
        "data": [1700000000000, 50000.0, 51000.0, 49500.0, 50800.0, 1000.0],
    }
    sent_count = await manager.broadcast(1, "1h", data)

    # Verify both received the message
    assert sent_count == 2
    mock_ws1.send_text.assert_called_once()
    mock_ws2.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_broadcast_no_subscribers():
    """Test broadcasting when there are no subscribers."""
    manager = ConnectionManager()

    data = {"type": "test", "message": "hello"}
    sent_count = await manager.broadcast(999, "1h", data)

    assert sent_count == 0


@pytest.mark.asyncio
async def test_connection_manager_multiple_subscriptions():
    """Test managing multiple different subscriptions."""
    manager = ConnectionManager()

    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws2.accept = AsyncMock()

    # Subscribe to different market/timeframes
    await manager.connect(mock_ws1, market_id=1, timeframe="1h")
    await manager.connect(mock_ws2, market_id=2, timeframe="4h")

    # Verify separate subscriptions
    assert manager.get_subscribers(1, "1h") == 1
    assert manager.get_subscribers(2, "4h") == 1
    assert manager.get_subscribers(1, "4h") == 0

    stats = manager.get_stats()
    assert stats["active_connections"] == 2
    assert stats["total_subscriptions"] == 2


@pytest.mark.asyncio
async def test_connection_manager_heartbeat():
    """Test sending heartbeat to connections."""
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    await manager.connect(mock_ws, market_id=1, timeframe="1h")

    # Send heartbeat
    result = await manager.send_heartbeat(mock_ws)

    assert result is True
    mock_ws.send_text.assert_called()
    # Verify heartbeat message format
    call_args = mock_ws.send_text.call_args[0][0]
    message = json.loads(call_args)
    assert message["type"] == "heartbeat"
    assert "timestamp" in message


@pytest.mark.asyncio
async def test_connection_manager_dead_connection_cleanup():
    """Test cleanup of dead connections during broadcast."""
    manager = ConnectionManager()

    # Create mock connections - one that works, one that fails
    mock_ws_good = AsyncMock()
    mock_ws_bad = AsyncMock()
    mock_ws_good.accept = AsyncMock()
    mock_ws_bad.accept = AsyncMock()
    mock_ws_good.send_text = AsyncMock()
    mock_ws_bad.send_text = AsyncMock(side_effect=Exception("Connection lost"))

    # Connect both
    await manager.connect(mock_ws_good, market_id=1, timeframe="1h")
    await manager.connect(mock_ws_bad, market_id=1, timeframe="1h")

    # Broadcast - should clean up the bad connection
    data = {"type": "test", "message": "hello"}
    sent_count = await manager.broadcast(1, "1h", data)

    # Only good connection should receive
    assert sent_count == 1

    # Bad connection should be removed
    assert manager.get_subscribers(1, "1h") == 1


@pytest.mark.asyncio
async def test_websocket_stats_endpoint(async_client):
    """Test WebSocket stats endpoint."""
    response = await async_client.get("/ws/stats")

    assert response.status_code == 200
    data = response.json()
    assert "active_connections" in data
    assert "total_subscriptions" in data
    assert "total_connections_served" in data
    assert "total_messages_sent" in data


@pytest.mark.skip(reason="TestClient conflicts with async event loop in pytest-asyncio")
def test_websocket_endpoint_sync():
    """Test WebSocket endpoint basic functionality (synchronous test)."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        with client.websocket_connect("/ws/data/ohlcv?market_id=1&timeframe=1h") as websocket:
            # Receive connection confirmation
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data["market_id"] == 1
            assert data["timeframe"] == "1h"
            assert "timestamp" in data

            # Send ping
            websocket.send_json({"type": "ping"})

            # Receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert "timestamp" in response