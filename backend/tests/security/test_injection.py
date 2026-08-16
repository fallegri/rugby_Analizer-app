"""Security tests for injection prevention.

Tests SQL injection, XSS, and oversized request body handling
across all API endpoints.
"""

import io
import json
import struct
from uuid import uuid4

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


class TestSQLInjection:
    """Tests for SQL injection prevention in query parameters."""

    def test_sql_injection_in_video_id(self, client):
        """Test SQL injection in video ID path parameter."""
        malicious_id = "'; DROP TABLE videos; --"
        response = client.get(f"/api/video/{malicious_id}")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_sql_injection_in_analysis_session(self, client):
        """Test SQL injection in analysis session ID."""
        malicious_id = "1 OR 1=1; --"
        response = client.get(f"/api/analysis/{malicious_id}/status")
        assert response.status_code == 404

    def test_sql_injection_in_calibration(self, client):
        """Test SQL injection in calibration endpoint."""
        response = client.post(
            "/api/calibration/auto",
            json={
                "image_data": "'; DELETE FROM calibrations; --",
                "width": 1920,
                "height": 1080,
            },
        )
        assert response.status_code in (200, 400, 422)

    def test_union_select_injection(self, client):
        """Test UNION SELECT injection attempt."""
        malicious = "' UNION SELECT username, password FROM users --"
        response = client.get(f"/api/video/{malicious}")
        assert response.status_code == 404

    def test_sql_injection_in_process_request(self, client):
        """Test SQL injection in process request body."""
        response = client.post(
            "/api/video/nonexistent/process",
            json={
                "mode": "single_player",
                "target_ids": [1],
                "calibration_id": "'; DROP TABLE sessions; --",
            },
        )
        assert response.status_code == 404


class TestXSSPrevention:
    """Tests for XSS content handling in AI prompts and responses."""

    def test_xss_in_ai_prompt_handled_safely(self, client, app):
        """Test that XSS in AI prompt is passed safely (not rendered)."""
        from src.core.enums import TrackingMode
        from src.core.models import AnalysisRequest

        service = app.state.analysis_service
        request = AnalysisRequest(
            video_id=uuid4(),
            mode=TrackingMode.SINGLE_PLAYER,
        )
        session_id = service.start_analysis(request)

        response = client.post(
            f"/api/analysis/{session_id}/ai-query",
            json={"prompt": "<script>alert('xss')</script>How fast was player 1?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "application/json" in response.headers.get("content-type", "")

    def test_xss_in_analysis_start_request(self, client):
        """Test XSS in analysis start request is handled."""
        response = client.post(
            "/api/analysis/start",
            json={
                "video_id": str(uuid4()),
                "mode": "single_player",
                "players": [
                    {
                        "player_id": "<img src=x onerror=alert('xss')>",
                        "bounding_box": [0, 0, 100, 100],
                    }
                ],
            },
        )
        assert response.status_code == 201

    def test_xss_in_video_filename(self, client):
        """Test XSS in uploaded filename."""
        content = bytearray(1024)
        content[0:4] = struct.pack(">I", 20)
        content[4:8] = b"ftyp"
        content[8:12] = b"isom"

        response = client.post(
            "/api/video/upload",
            files={
                "file": (
                    "<script>alert('xss')</script>.mp4",
                    io.BytesIO(bytes(content)),
                    "video/mp4",
                )
            },
        )
        if response.status_code == 201:
            data = response.json()
            assert "<script>" not in data.get("id", "")

    def test_response_content_type_is_json(self, client):
        """Test that API responses are JSON, preventing XSS rendering."""
        response = client.get("/api/health")
        assert "application/json" in response.headers.get("content-type", "")


class TestOversizedRequests:
    """Tests for oversized request body handling."""

    def test_oversized_json_body(self, client):
        """Test that oversized JSON body is handled."""
        large_data = {
            "video_id": str(uuid4()),
            "mode": "single_player",
            "players": [{"player_id": f"player_{i}", "bounding_box": [0, 0, 100, 100]} for i in range(10000)],
        }
        response = client.post("/api/analysis/start", json=large_data)
        assert response.status_code in (201, 400, 413, 422)

    def test_oversized_ai_prompt(self, client, app):
        """Test that oversized AI prompt is rejected via validation."""
        from src.core.enums import TrackingMode
        from src.core.models import AnalysisRequest

        service = app.state.analysis_service
        request = AnalysisRequest(
            video_id=uuid4(),
            mode=TrackingMode.SINGLE_PLAYER,
        )
        session_id = service.start_analysis(request)

        response = client.post(
            f"/api/analysis/{session_id}/ai-query",
            json={"prompt": "x" * 5001},
        )
        assert response.status_code == 422

    def test_oversized_file_upload(self):
        """Test that validate_file_upload rejects files exceeding the limit."""
        from src.api.security import validate_file_upload

        content = b"\x00" * (10 * 1024 * 1024)
        is_valid, error = validate_file_upload(
            content=content,
            filename="large.mp4",
            max_size=1 * 1024 * 1024,
        )
        assert not is_valid
        assert "exceeds" in error.lower()

    def test_deeply_nested_json(self, client):
        """Test handling of deeply nested JSON structures."""
        data = {"mode": "single_player", "video_id": str(uuid4())}
        nested = data
        for i in range(50):
            nested["nested"] = {"level": i}
            nested = nested["nested"]

        response = client.post("/api/analysis/start", json=data)
        assert response.status_code in (201, 400, 422)
