"""Integration tests for AI analysis with context injection.

Tests that the AI query endpoint correctly injects analysis context
into prompts and handles various states.
"""

import io
import struct
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture
def app():
    """Create a fresh test app instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_mp4_content():
    """Create mock MP4 content with valid magic bytes."""
    content = bytearray(1024)
    content[0:4] = struct.pack(">I", 20)
    content[4:8] = b"ftyp"
    content[8:12] = b"isom"
    return bytes(content)


@pytest.fixture
def completed_session(app, client, mock_mp4_content):
    """Create a completed analysis session for testing."""
    # Upload video
    upload_response = client.post(
        "/api/video/upload",
        files={"file": ("test.mp4", io.BytesIO(mock_mp4_content), "video/mp4")},
    )
    video_id = upload_response.json()["id"]

    # Start analysis
    start_response = client.post(
        "/api/analysis/start",
        json={"video_id": video_id, "mode": "single_player"},
    )
    session_id = start_response.json()["session_id"]

    # Mark as completed using the app's analysis service instance
    service = app.state.analysis_service
    service.mark_completed(
        session_id,
        {
            "total_frames": 300,
            "fps": 30.0,
            "duration_s": 10.0,
            "analytics": {
                "1": {"max_speed": 28.5, "avg_speed": 15.2, "total_distance": 0.152},
                "2": {"max_speed": 22.0, "avg_speed": 11.0, "total_distance": 0.11},
            },
        },
    )

    return session_id


class TestAIQueryEndpoint:
    """Tests for the AI query endpoint with context injection."""

    def test_ai_query_with_completed_analysis(self, client, completed_session):
        """Test AI query with completed analysis context."""
        response = client.post(
            f"/api/analysis/{completed_session}/ai-query",
            json={"prompt": "What was the fastest player?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == completed_session
        assert data["prompt"] == "What was the fastest player?"
        assert data["context_used"] is True

    def test_ai_query_without_results(self, client, mock_mp4_content):
        """Test AI query when analysis is not yet complete."""
        # Upload and start
        upload_response = client.post(
            "/api/video/upload",
            files={"file": ("test.mp4", io.BytesIO(mock_mp4_content), "video/mp4")},
        )
        video_id = upload_response.json()["id"]

        start_response = client.post(
            "/api/analysis/start",
            json={"video_id": video_id, "mode": "ball_only"},
        )
        session_id = start_response.json()["session_id"]

        # Query AI (no completed results yet)
        response = client.post(
            f"/api/analysis/{session_id}/ai-query",
            json={"prompt": "Describe the ball trajectory"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["context_used"] is False

    def test_ai_query_nonexistent_session(self, client):
        """Test AI query for non-existent session returns 404."""
        response = client.post(
            f"/api/analysis/{uuid4()}/ai-query",
            json={"prompt": "What happened?"},
        )
        assert response.status_code == 404

    def test_ai_query_empty_prompt(self, client, completed_session):
        """Test AI query with empty prompt is rejected."""
        response = client.post(
            f"/api/analysis/{completed_session}/ai-query",
            json={"prompt": ""},
        )
        assert response.status_code == 422

    def test_ai_query_oversized_prompt(self, client, completed_session):
        """Test AI query with oversized prompt is rejected."""
        response = client.post(
            f"/api/analysis/{completed_session}/ai-query",
            json={"prompt": "x" * 5001},
        )
        assert response.status_code == 422

    def test_ai_query_response_format(self, client, completed_session):
        """Test AI query response has expected format."""
        response = client.post(
            f"/api/analysis/{completed_session}/ai-query",
            json={"prompt": "Analyze player movement patterns"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "prompt" in data
        assert "response" in data
        assert "context_used" in data


class TestContextInjection:
    """Tests verifying that analysis context is properly injected into prompts."""

    def test_context_includes_video_id(self, client, completed_session):
        """Test that context includes the video ID."""
        response = client.post(
            f"/api/analysis/{completed_session}/ai-query",
            json={"prompt": "test"},
        )
        assert response.status_code == 200
        assert response.json()["context_used"] is True

    def test_context_includes_analytics_data(self, client, completed_session):
        """Test that context includes player analytics data."""
        response = client.post(
            f"/api/analysis/{completed_session}/ai-query",
            json={"prompt": "Who was fastest?"},
        )
        data = response.json()
        assert data["context_used"] is True
        assert data["session_id"] == completed_session
