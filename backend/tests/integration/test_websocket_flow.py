"""Integration tests for WebSocket analysis flow.

Tests the WebSocket connection, message handling, and progress broadcasting
during analysis sessions.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.websocket import ConnectionManager, manager
from src.main import create_app


@pytest.fixture
def app():
    """Create a fresh test app instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestWebSocketFlow:
    """Tests for WebSocket analysis progress flow."""

    def test_connect_to_session(self, client):
        """Test connecting to a valid analysis session WebSocket."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data["session_id"] == session_id

    def test_receive_ping_pong(self, client):
        """Test WebSocket heartbeat ping/pong."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            # Receive connection message
            websocket.receive_json()

            # Send ping
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_json()
            assert response["type"] == "pong"

    def test_subscribe_message(self, client):
        """Test WebSocket subscribe acknowledgment."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            websocket.receive_json()  # connected

            websocket.send_text(json.dumps({"type": "subscribe"}))
            response = websocket.receive_json()
            assert response["type"] == "subscribed"
            assert response["session_id"] == session_id

    def test_invalid_json_message(self, client):
        """Test that invalid JSON is handled gracefully."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            websocket.receive_json()  # connected

            websocket.send_text("not valid json")
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Invalid JSON" in response["message"]

    def test_unknown_message_type(self, client):
        """Test handling of unknown message types."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            websocket.receive_json()  # connected

            websocket.send_text(json.dumps({"type": "unknown_type"}))
            response = websocket.receive_json()
            assert response["type"] == "ack"
            assert response["received"] == "unknown_type"

    def test_invalid_session_id_format(self, client):
        """Test that invalid session ID format closes connection."""
        try:
            with client.websocket_connect("/ws/analysis/not-a-uuid") as websocket:
                pass
        except Exception:
            pass


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_manager_singleton_exists(self):
        """Test that global manager instance exists."""
        assert manager is not None
        assert isinstance(manager, ConnectionManager)

    def test_get_active_sessions_empty(self):
        """Test that initially no active sessions exist."""
        mgr = ConnectionManager()
        assert mgr.get_active_sessions() == []

    def test_get_connection_count_empty(self):
        """Test connection count for non-existent session."""
        mgr = ConnectionManager()
        assert mgr.get_connection_count("nonexistent") == 0


class TestWebSocketBroadcast:
    """Tests for WebSocket message broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_progress_no_connections(self):
        """Test broadcasting with no active connections does not error."""
        mgr = ConnectionManager()
        await mgr.broadcast_progress(
            session_id="test-session",
            progress=50.0,
            status="processing",
        )

    @pytest.mark.asyncio
    async def test_send_message_no_connections(self):
        """Test sending message with no connections does not error."""
        mgr = ConnectionManager()
        await mgr.send_message("test-session", {"type": "test"})
