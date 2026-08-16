"""WebSocket endpoint for real-time analysis updates.

Provides real-time progress updates during video processing sessions.
Includes connection management, heartbeat, and graceful disconnection.
"""

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.security import (
    rate_limit_websocket,
    release_websocket_connection,
    validate_websocket_origin,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates.

    Tracks active connections per session and provides methods
    for broadcasting messages to session subscribers.
    """

    def __init__(self):
        self._active_connections: dict[str, list[WebSocket]] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to accept.
            session_id: The analysis session ID to subscribe to.
        """
        await websocket.accept()
        if session_id not in self._active_connections:
            self._active_connections[session_id] = []
        self._active_connections[session_id].append(websocket)
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a WebSocket connection from tracking.

        Args:
            websocket: The WebSocket connection to remove.
            session_id: The session ID to unsubscribe from.
        """
        if session_id in self._active_connections:
            self._active_connections[session_id] = [
                ws for ws in self._active_connections[session_id] if ws != websocket
            ]
            if not self._active_connections[session_id]:
                del self._active_connections[session_id]
        logger.info(f"WebSocket disconnected from session: {session_id}")

    async def send_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connections in a session.

        Args:
            session_id: The session to broadcast to.
            message: The message dict to send as JSON.
        """
        if session_id not in self._active_connections:
            return

        disconnected = []
        for websocket in self._active_connections[session_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, session_id)

    async def broadcast_progress(
        self, session_id: str, progress: float, status: str, data: dict | None = None
    ) -> None:
        """Broadcast a progress update for a session.

        Args:
            session_id: The session ID.
            progress: Progress percentage (0-100).
            status: Current status string.
            data: Optional additional data.
        """
        message = {
            "type": "progress",
            "session_id": session_id,
            "progress": progress,
            "status": status,
        }
        if data:
            message["data"] = data
        await self.send_message(session_id, message)

    def get_active_sessions(self) -> list[str]:
        """Get list of sessions with active connections."""
        return list(self._active_connections.keys())

    def get_connection_count(self, session_id: str) -> int:
        """Get number of active connections for a session."""
        return len(self._active_connections.get(session_id, []))


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/analysis/{session_id}")
async def websocket_analysis(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time analysis progress updates.

    Accepts connections for a specific analysis session and sends
    progress updates as JSON messages. Supports heartbeat pings.
    Validates origin, enforces per-IP connection limits, and cleans
    up connection slots on disconnect.

    Args:
        websocket: The WebSocket connection.
        session_id: UUID of the analysis session to monitor.
    """
    # Validate session_id format
    try:
        UUID(session_id)
    except ValueError:
        await websocket.close(code=4001, reason="Invalid session ID format")
        return

    # Validate origin
    origin = websocket.headers.get("origin")
    if not validate_websocket_origin(origin):
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # Extract client IP for rate limiting
    client_ip = websocket.client.host if websocket.client else "unknown"

    # Enforce per-IP connection limit
    if not rate_limit_websocket(client_ip):
        await websocket.close(code=4029, reason="Too many connections")
        return

    await manager.connect(websocket, session_id)

    # Send initial connection confirmation
    await websocket.send_json(
        {
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to analysis session",
        }
    )

    try:
        while True:
            # Wait for messages from client (heartbeat pings, commands)
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"type": "error", "message": "Invalid JSON format"}
                )
                continue

            msg_type = message.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "session_id": session_id,
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "ack",
                        "received": msg_type,
                    }
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        release_websocket_connection(client_ip)
        logger.info(f"Client disconnected from session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(websocket, session_id)
        release_websocket_connection(client_ip)
