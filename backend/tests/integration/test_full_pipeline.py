"""Integration tests for the full analysis pipeline.

Tests the complete flow: upload video -> start analysis -> check status -> get results.
Uses FastAPI TestClient and mocks CV components.
"""

import io
import struct
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.services.analysis_service import AnalysisService


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
    """Create mock MP4 file content with valid magic bytes."""
    # MP4 files have 'ftyp' at offset 4
    content = bytearray(1024)
    content[0:4] = struct.pack(">I", 20)  # box size
    content[4:8] = b"ftyp"  # box type
    content[8:12] = b"isom"  # major brand
    return bytes(content)


class TestFullPipeline:
    """Tests for the complete analysis pipeline flow."""

    def test_upload_and_start_analysis(self, client, mock_mp4_content):
        """Test uploading a video and starting analysis."""
        # Upload video
        upload_response = client.post(
            "/api/video/upload",
            files={"file": ("test_video.mp4", io.BytesIO(mock_mp4_content), "video/mp4")},
        )
        assert upload_response.status_code == 201
        video_data = upload_response.json()
        video_id = video_data["id"]

        # Start analysis
        analysis_response = client.post(
            "/api/analysis/start",
            json={
                "video_id": video_id,
                "mode": "single_player",
            },
        )
        assert analysis_response.status_code == 201
        assert "session_id" in analysis_response.json()

    def test_check_analysis_status(self, client, mock_mp4_content):
        """Test checking analysis status after starting."""
        # Upload
        upload_response = client.post(
            "/api/video/upload",
            files={"file": ("test.mp4", io.BytesIO(mock_mp4_content), "video/mp4")},
        )
        video_id = upload_response.json()["id"]

        # Start analysis
        start_response = client.post(
            "/api/analysis/start",
            json={"video_id": video_id, "mode": "ball_only"},
        )
        session_id = start_response.json()["session_id"]

        # Check status - background task fires immediately but fails since
        # no VideoProcessor is available in the MVP (GPU not present)
        status_response = client.get(f"/api/analysis/{session_id}/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["session_id"] == session_id
        assert status_data["status"] == "failed"

    def test_get_results_before_completion(self, client, mock_mp4_content):
        """Test that getting results before completion returns error."""
        # Upload
        upload_response = client.post(
            "/api/video/upload",
            files={"file": ("test.mp4", io.BytesIO(mock_mp4_content), "video/mp4")},
        )
        video_id = upload_response.json()["id"]

        # Start analysis
        start_response = client.post(
            "/api/analysis/start",
            json={"video_id": video_id, "mode": "group_tracking"},
        )
        session_id = start_response.json()["session_id"]

        # Try to get results (should fail - not complete)
        results_response = client.get(f"/api/analysis/{session_id}/results")
        assert results_response.status_code == 400
        assert "not complete" in results_response.json()["detail"].lower()

    def test_get_results_after_completion(self, client, mock_mp4_content):
        """Test getting results after manually marking completion."""
        # Upload
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

        # Manually mark the session as completed (simulating background task)
        from src.api.routes.analysis import get_analysis_service

        service = get_analysis_service()
        service.mark_completed(
            session_id,
            {
                "total_frames": 100,
                "fps": 30.0,
                "duration_s": 3.33,
                "analytics": {"1": {"max_speed": 25.0, "avg_speed": 12.5, "total_distance": 0.5}},
            },
        )

        # Get results
        results_response = client.get(f"/api/analysis/{session_id}/results")
        assert results_response.status_code == 200
        results_data = results_response.json()
        assert results_data["session_id"] == session_id
        assert results_data["status"] == "completed"
        assert results_data["results"]["total_frames"] == 100


class TestErrorCases:
    """Tests for error handling in the pipeline."""

    def test_invalid_session_id_status(self, client):
        """Test requesting status for non-existent session."""
        response = client.get(f"/api/analysis/{uuid4()}/status")
        assert response.status_code == 404

    def test_invalid_session_id_results(self, client):
        """Test requesting results for non-existent session."""
        response = client.get(f"/api/analysis/{uuid4()}/results")
        assert response.status_code == 404

    def test_invalid_video_id_format(self, client):
        """Test starting analysis with invalid video ID."""
        response = client.post(
            "/api/analysis/start",
            json={"video_id": "not-a-uuid", "mode": "single_player"},
        )
        assert response.status_code in (400, 422)
        assert "invalid" in response.json()["detail"].lower()

    def test_invalid_tracking_mode(self, client):
        """Test starting analysis with invalid tracking mode."""
        response = client.post(
            "/api/analysis/start",
            json={"video_id": str(uuid4()), "mode": "invalid_mode"},
        )
        assert response.status_code == 422

    def test_upload_invalid_file_type(self, client):
        """Test uploading a file with invalid extension."""
        content = b"fake file content for testing"
        response = client.post(
            "/api/video/upload",
            files={"file": ("script.php", io.BytesIO(content), "application/x-php")},
        )
        assert response.status_code in (400, 422)

    def test_upload_empty_filename(self, client):
        """Test uploading with empty filename."""
        content = b"some content"
        response = client.post(
            "/api/video/upload",
            files={"file": ("", io.BytesIO(content), "video/mp4")},
        )
        assert response.status_code in (400, 422)
