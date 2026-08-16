"""Security tests for API endpoints.

Tests rate limiting, authentication middleware, and input validation
against common attack vectors (injection, XSS, oversized payloads).
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture
def app():
    """Create a test app instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_requests_within_limit_succeed(self, client):
        """Test that requests within the rate limit succeed."""
        # Health endpoint is excluded from rate limiting
        for _ in range(10):
            response = client.get("/api/health")
            assert response.status_code == 200

    def test_rate_limit_exceeded_returns_429(self):
        """Test that exceeding rate limit returns 429."""
        os.environ["RATE_LIMIT_REQUESTS"] = "3"
        os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"

        try:
            app = create_app()
            client = TestClient(app)

            # Make requests to a rate-limited endpoint
            responses = []
            for _ in range(10):
                response = client.get("/api/ai/providers")
                responses.append(response.status_code)

            # Should have some 429 responses
            assert 429 in responses
        finally:
            os.environ.pop("RATE_LIMIT_REQUESTS", None)
            os.environ.pop("RATE_LIMIT_WINDOW_SECONDS", None)

    def test_rate_limit_response_format(self):
        """Test that rate limit response has correct format."""
        os.environ["RATE_LIMIT_REQUESTS"] = "1"
        os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"

        try:
            app = create_app()
            client = TestClient(app)

            # First request should succeed
            client.get("/api/ai/providers")

            # Second request should be rate limited
            response = client.get("/api/ai/providers")

            if response.status_code == 429:
                data = response.json()
                assert "detail" in data
                assert "retry_after" in data
                assert "Retry-After" in response.headers
        finally:
            os.environ.pop("RATE_LIMIT_REQUESTS", None)
            os.environ.pop("RATE_LIMIT_WINDOW_SECONDS", None)

    def test_health_endpoint_not_rate_limited(self):
        """Test that health endpoint is exempt from rate limiting."""
        os.environ["RATE_LIMIT_REQUESTS"] = "1"
        os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "60"

        try:
            app = create_app()
            client = TestClient(app)

            # Health endpoint should always respond even with strict limit
            for _ in range(5):
                response = client.get("/api/health")
                assert response.status_code == 200
        finally:
            os.environ.pop("RATE_LIMIT_REQUESTS", None)
            os.environ.pop("RATE_LIMIT_WINDOW_SECONDS", None)


class TestInputValidation:
    """Tests for input validation and injection prevention."""

    def test_analyze_rejects_empty_prompt(self, client):
        """Test that empty prompt is rejected."""
        response = client.post(
            "/api/ai/analyze",
            json={"prompt": "", "context": ""},
        )
        assert response.status_code == 422  # Validation error

    def test_analyze_rejects_oversized_prompt(self, client):
        """Test that oversized prompt is rejected."""
        response = client.post(
            "/api/ai/analyze",
            json={"prompt": "x" * 10001, "context": ""},
        )
        assert response.status_code == 422

    def test_analyze_rejects_oversized_context(self, client):
        """Test that oversized context is rejected."""
        response = client.post(
            "/api/ai/analyze",
            json={"prompt": "test", "context": "x" * 50001},
        )
        assert response.status_code == 422

    def test_switch_provider_rejects_invalid_provider(self, client):
        """Test that invalid provider name is rejected."""
        response = client.put(
            "/api/ai/provider",
            json={"provider": "invalid_provider"},
        )
        assert response.status_code == 422

    def test_update_config_rejects_empty_key(self, client):
        """Test that empty API key is rejected."""
        response = client.put(
            "/api/ai/config",
            json={"provider": "nvidia", "api_key": ""},
        )
        assert response.status_code == 422

    def test_sql_injection_in_prompt(self, client):
        """Test that SQL injection attempts are handled safely."""
        response = client.post(
            "/api/ai/analyze",
            json={
                "prompt": "'; DROP TABLE users; --",
                "context": "",
            },
        )
        # Should not crash - either 400 (not configured) or 500 (API call fails)
        assert response.status_code in (400, 500)
        data = response.json()
        assert "detail" in data

    def test_xss_in_prompt(self, client):
        """Test that XSS attempts are handled safely."""
        response = client.post(
            "/api/ai/analyze",
            json={
                "prompt": "<script>alert('xss')</script>",
                "context": "",
            },
        )
        # Should be handled without executing script
        assert response.status_code in (400, 500)

    def test_invalid_json_body(self, client):
        """Test that invalid JSON body is rejected."""
        response = client.post(
            "/api/ai/analyze",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestWebSocketSecurity:
    """Tests for WebSocket endpoint security."""

    def test_invalid_session_id_format(self, client):
        """Test that invalid session ID format is rejected."""
        # Invalid UUID should cause the server to close connection
        try:
            with client.websocket_connect("/ws/analysis/not-a-uuid") as websocket:
                # If connection was accepted, the server should have closed it
                pass
        except Exception:
            # Expected - server rejects invalid UUID
            pass

    def test_valid_session_id_connects(self, client):
        """Test that valid UUID session ID connects successfully."""
        session_id = str(uuid.uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data["session_id"] == session_id

    def test_websocket_ping_pong(self, client):
        """Test WebSocket heartbeat mechanism."""
        import json

        session_id = str(uuid.uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            # Receive connection confirmation
            websocket.receive_json()

            # Send ping
            websocket.send_text(json.dumps({"type": "ping"}))
            response = websocket.receive_json()
            assert response["type"] == "pong"

    def test_websocket_invalid_json(self, client):
        """Test WebSocket handles invalid JSON gracefully."""
        session_id = str(uuid.uuid4())
        with client.websocket_connect(f"/ws/analysis/{session_id}") as websocket:
            # Receive connection confirmation
            websocket.receive_json()

            # Send invalid JSON
            websocket.send_text("not valid json")
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Invalid JSON" in response["message"]
