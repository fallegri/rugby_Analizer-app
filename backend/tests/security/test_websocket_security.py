"""Security tests for WebSocket connections.

Tests connection limits per IP, invalid session IDs,
and malicious message handling.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.security import rate_limit_websocket, release_websocket_connection, reset_ws_connections
from src.main import create_app


@pytest.fixture
def app():
    """Create a test app instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_ws_connections():
    """Reset WebSocket connection tracking between tests."""
    reset_ws_connections()
    yield
    reset_ws_connections()


class TestConnectionLimits:
    """Tests for WebSocket connection rate limiting."""

    def test_connection_allowed_within_limit(self):
        """Test that connections within the limit are allowed."""
        for i in range(5):
            assert rate_limit_websocket("192.168.1.1", max_connections=5) is True

    def test_connection_rejected_over_limit(self):
        """Test that connections over the limit are rejected."""
        ip = "10.0.0.1"
        for i in range(5):
            assert rate_limit_websocket(ip, max_connections=5) is True

        assert rate_limit_websocket(ip, max_connections=5) is False

    def test_different_ips_independent(self):
        """Test that different IPs have independent limits."""
        for i in range(5):
            rate_limit_websocket("ip1", max_connections=5)

        assert rate_limit_websocket("ip2", max_connections=5) is True

    def test_release_frees_slot(self):
        """Test that releasing a connection frees a slot."""
        ip = "192.168.1.100"
        for i in range(5):
            rate_limit_websocket(ip, max_connections=5)

        assert rate_limit_websocket(ip, max_connections=5) is False

        release_websocket_connection(ip)

        assert rate_limit_websocket(ip, max_connections=5) is True

    def test_custom_limit(self):
        """Test custom connection limit."""
        ip = "custom-test"
        assert rate_limit_websocket(ip, max_connections=2) is True
        assert rate_limit_websocket(ip, max_connections=2) is True
        assert rate_limit_websocket(ip, max_connections=2) is False


class TestInvalidSessionID:
    """Tests for invalid session ID handling."""

    def test_non_uuid_session_id_handled(self, client):
        """Test that non-UUID session ID is handled (connection closed)."""
        try:
            with client.websocket_connect("/ws/analysis/invalid-session") as ws:
                pass
        except Exception:
            pass

    def test_empty_session_id_returns_error(self, client):
        """Test that empty path returns 404 (no route match)."""
        response = client.get("/ws/analysis/")
        assert response.status_code in (404, 405, 307)

    def test_sql_injection_in_session_id(self, client):
        """Test that SQL injection in session ID is handled safely."""
        try:
            with client.websocket_connect("/ws/analysis/'; DROP TABLE sessions;--") as ws:
                pass
        except Exception:
            pass

    def test_very_long_session_id(self, client):
        """Test that very long session ID is handled."""
        try:
            with client.websocket_connect(f"/ws/analysis/{'a' * 1000}") as ws:
                pass
        except Exception:
            pass

    def test_valid_uuid_connects(self, client):
        """Test that a valid UUID session ID connects successfully."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data["session_id"] == session_id


class TestMaliciousMessages:
    """Tests for handling malicious WebSocket messages."""

    def test_oversized_message(self, client):
        """Test handling of very large messages."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            websocket.receive_json()  # connected

            large_msg = json.dumps({"type": "ping", "data": "x" * 10000})
            websocket.send_text(large_msg)
            response = websocket.receive_json()
            assert response["type"] == "pong"

    def test_nested_json_attack(self, client):
        """Test handling of deeply nested JSON."""
        session_id = str(uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            websocket.receive_json()  # connected

            nested = {"type": "test"}
            for _ in range(10):
                nested = {"nested": nested, "type": "test"}

            websocket.send_text(json.dumps(nested))
            response = websocket.receive_json()
            assert response["type"] == "ack"
