"""WebSocket connection manager and endpoints for real-time data streaming."""
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from weakref import WeakSet

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time data streaming.

    Features:
    - Multi-client connection management
    - Subscription-based message routing
    - Heartbeat/ping-pong for connection health
    - Automatic cleanup of disconnected clients
    """

    def __init__(self):
        # Active connections grouped by subscription key
        # Key: f"{market_id}:{timeframe}", Value: WeakSet of WebSocket connections
        self._subscriptions: dict[str, WeakSet[WebSocket]] = defaultdict(WeakSet)

        # Reverse mapping: connection -> set of subscription keys
        self._connection_subscriptions: dict[WebSocket, set[str]] = defaultdict(set)

        # Connection metadata
        self._connection_meta: dict[WebSocket, dict] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # Stats
        self._total_connections = 0
        self._total_messages_sent = 0

    async def connect(self, websocket: WebSocket, market_id: int, timeframe: str) -> None:
        """Accept a new WebSocket connection and subscribe to a market/timeframe.

        Args:
            websocket: The WebSocket connection
            market_id: Market ID to subscribe to
            timeframe: Timeframe to subscribe to (e.g., "1h", "4h", "1d")
        """
        await websocket.accept()

        async with self._lock:
            sub_key = self._make_sub_key(market_id, timeframe)
            self._subscriptions[sub_key].add(websocket)
            self._connection_subscriptions[websocket].add(sub_key)
            self._connection_meta[websocket] = {
                "connected_at": datetime.now(timezone.utc),
                "market_id": market_id,
                "timeframe": timeframe,
            }
            self._total_connections += 1

        logger.info(
            f"WebSocket connected: market_id={market_id}, timeframe={timeframe}, "
            f"active_connections={self._get_connection_count()}"
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Handle WebSocket disconnection and cleanup subscriptions.

        Args:
            websocket: The WebSocket connection to disconnect
        """
        async with self._lock:
            # Get all subscriptions for this connection
            sub_keys = self._connection_subscriptions.get(websocket, set())

            # Remove from all subscription groups
            for sub_key in sub_keys:
                if websocket in self._subscriptions.get(sub_key, set()):
                    self._subscriptions[sub_key].discard(websocket)
                    # Clean up empty subscription groups
                    if not self._subscriptions[sub_key]:
                        del self._subscriptions[sub_key]

            # Remove connection metadata
            if websocket in self._connection_subscriptions:
                del self._connection_subscriptions[websocket]
            if websocket in self._connection_meta:
                del self._connection_meta[websocket]

        logger.info(
            f"WebSocket disconnected, active_connections={self._get_connection_count()}"
        )

    async def broadcast(self, market_id: int, timeframe: str, data: dict) -> int:
        """Broadcast data to all subscribers of a market/timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe
            data: Data to broadcast (will be JSON encoded)

        Returns:
            Number of clients that received the message
        """
        sub_key = self._make_sub_key(market_id, timeframe)
        connections = self._subscriptions.get(sub_key, set())

        if not connections:
            return 0

        message = json.dumps(data)
        sent_count = 0
        dead_connections = []

        for websocket in list(connections):
            try:
                await websocket.send_text(message)
                sent_count += 1
                self._total_messages_sent += 1
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                dead_connections.append(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            await self.disconnect(ws)

        return sent_count

    async def send_heartbeat(self, websocket: WebSocket) -> bool:
        """Send a heartbeat/ping message to a connection.

        Args:
            websocket: The WebSocket connection

        Returns:
            True if heartbeat was sent successfully, False otherwise
        """
        try:
            await websocket.send_text(json.dumps({"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}))
            return True
        except Exception:
            return False

    def get_subscribers(self, market_id: int, timeframe: str) -> int:
        """Get the number of subscribers for a market/timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe

        Returns:
            Number of active subscribers
        """
        sub_key = self._make_sub_key(market_id, timeframe)
        return len(self._subscriptions.get(sub_key, set()))

    def get_stats(self) -> dict:
        """Get connection statistics.

        Returns:
            Dictionary with connection stats
        """
        return {
            "active_connections": self._get_connection_count(),
            "total_subscriptions": len(self._subscriptions),
            "total_connections_served": self._total_connections,
            "total_messages_sent": self._total_messages_sent,
            "subscription_details": {
                sub_key: len(conns)
                for sub_key, conns in self._subscriptions.items()
            },
        }

    def _make_sub_key(self, market_id: int, timeframe: str) -> str:
        """Create a subscription key from market_id and timeframe."""
        return f"{market_id}:{timeframe}"

    def _get_connection_count(self) -> int:
        """Get the total number of active connections."""
        return len(self._connection_meta)


# Global connection manager instance
manager = ConnectionManager()


# ============ WebSocket Endpoints ============


@router.websocket("/ws/data/ohlcv")
async def websocket_ohlcv(
    websocket: WebSocket,
    market_id: int,
    timeframe: str,
):
    """WebSocket endpoint for real-time OHLCV data streaming.

    Args:
        websocket: WebSocket connection
        market_id: Market ID to subscribe to
        timeframe: Timeframe to subscribe to (e.g., "1h", "4h", "1d")

    Message types sent to clients:
    - "connected": Confirmation of successful connection
    - "ohlcv_update": Real-time OHLCV data
    - "heartbeat": Periodic heartbeat for connection health
    - "error": Error messages
    """
    await manager.connect(websocket, market_id, timeframe)

    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "market_id": market_id,
            "timeframe": timeframe,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        # Main message loop - handle incoming messages from client
        while True:
            try:
                # Wait for messages from client (with timeout for heartbeat)
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # 30 second timeout
                )

                # Parse and handle the message
                try:
                    data = json.loads(message)
                    await _handle_client_message(websocket, market_id, timeframe, data)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON message",
                    }))

            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                if not await manager.send_heartbeat(websocket):
                    logger.warning("Heartbeat failed, closing connection")
                    break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: market_id={market_id}, timeframe={timeframe}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket)


async def _handle_client_message(
    websocket: WebSocket,
    market_id: int,
    timeframe: str,
    data: dict,
) -> None:
    """Handle incoming message from WebSocket client.

    Args:
        websocket: WebSocket connection
        market_id: Current market ID subscription
        timeframe: Current timeframe subscription
        data: Parsed message data
    """
    msg_type = data.get("type")

    if msg_type == "ping":
        # Respond to ping with pong
        await websocket.send_text(json.dumps({
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

    elif msg_type == "subscribe":
        # Handle subscription change (future: support multiple subscriptions)
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Subscription changes not yet supported. Create new connection.",
        }))

    elif msg_type == "unsubscribe":
        # Handle unsubscription
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Unsubscription not yet supported. Close connection instead.",
        }))

    else:
        # Unknown message type
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        }))


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return manager.get_stats()