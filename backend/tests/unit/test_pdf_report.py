"""Tests for the PDF Report Service."""

import pytest

from src.services.pdf_report_service import PDFReportService


@pytest.fixture
def pdf_service():
    """Create a PDFReportService instance."""
    return PDFReportService()


@pytest.fixture
def mock_session_data():
    """Create mock session data with players, routes, and sprints."""
    return {
        "session_id": "test-session-001",
        "video_id": "video-uuid-001",
        "mode": "group_tracking",
        "status": "completed",
        "results": {
            "total_frames": 900,
            "fps": 30,
            "duration_s": 30.0,
            "players": [
                {
                    "player_id": "1",
                    "total_distance_km": 0.150,
                    "max_speed_kmh": 28.5,
                    "avg_speed_kmh": 12.3,
                    "sprint_count": 3,
                    "sprints": [
                        {"start_time": 2.0, "end_time": 4.0, "max_speed": 25.0, "distance": 0.03},
                        {"start_time": 10.0, "end_time": 12.5, "max_speed": 28.5, "distance": 0.04},
                        {"start_time": 20.0, "end_time": 22.0, "max_speed": 26.0, "distance": 0.03},
                    ],
                    "route": [
                        {"x": 100, "y": 200, "timestamp": 0.0, "speed": 5.0},
                        {"x": 110, "y": 210, "timestamp": 1.0, "speed": 8.0},
                        {"x": 130, "y": 220, "timestamp": 2.0, "speed": 15.0},
                        {"x": 160, "y": 230, "timestamp": 3.0, "speed": 25.0},
                        {"x": 200, "y": 240, "timestamp": 4.0, "speed": 20.0},
                        {"x": 220, "y": 250, "timestamp": 5.0, "speed": 10.0},
                        {"x": 230, "y": 260, "timestamp": 6.0, "speed": 6.0},
                    ],
                },
                {
                    "player_id": "2",
                    "total_distance_km": 0.120,
                    "max_speed_kmh": 22.0,
                    "avg_speed_kmh": 10.5,
                    "sprint_count": 1,
                    "sprints": [
                        {"start_time": 5.0, "end_time": 7.0, "max_speed": 22.0, "distance": 0.025},
                    ],
                    "route": [
                        {"x": 300, "y": 100, "timestamp": 0.0, "speed": 3.0},
                        {"x": 310, "y": 120, "timestamp": 1.0, "speed": 7.0},
                        {"x": 320, "y": 150, "timestamp": 2.0, "speed": 12.0},
                        {"x": 330, "y": 180, "timestamp": 3.0, "speed": 18.0},
                        {"x": 340, "y": 200, "timestamp": 4.0, "speed": 22.0},
                        {"x": 350, "y": 210, "timestamp": 5.0, "speed": 15.0},
                    ],
                },
            ],
            "plays": [
                {"type": "tackle", "time": 5.5, "description": "Player 1 tackled by defender"},
                {"type": "pass", "time": 12.0, "description": "Player 1 pass to Player 2"},
            ],
        },
    }


@pytest.fixture
def mock_session_empty_players():
    """Create mock session data with empty players list."""
    return {
        "session_id": "test-session-002",
        "video_id": "video-uuid-002",
        "mode": "single_player",
        "status": "completed",
        "results": {
            "total_frames": 300,
            "fps": 30,
            "duration_s": 10.0,
            "players": [],
            "plays": [],
        },
    }


class TestPDFReportService:
    """Tests for PDFReportService."""

    def test_generate_report_returns_bytes(self, pdf_service, mock_session_data):
        """Test that generate_report returns non-empty bytes."""
        result = pdf_service.generate_report(mock_session_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_report_starts_with_pdf_header(self, pdf_service, mock_session_data):
        """Test that generated PDF starts with PDF magic bytes."""
        result = pdf_service.generate_report(mock_session_data)
        assert result[:5] == b"%PDF-"

    def test_generate_report_with_empty_players(self, pdf_service, mock_session_empty_players):
        """Test PDF generation with empty players list (edge case)."""
        result = pdf_service.generate_report(mock_session_empty_players)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:5] == b"%PDF-"

    def test_generate_report_with_no_results(self, pdf_service):
        """Test PDF generation with missing results key."""
        session_data = {
            "session_id": "test-session-003",
            "video_id": "video-uuid-003",
            "mode": "ball_only",
            "status": "completed",
            "results": None,
        }
        result = pdf_service.generate_report(session_data)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:5] == b"%PDF-"

    def test_generate_report_with_minimal_data(self, pdf_service):
        """Test PDF generation with minimal session data."""
        session_data = {
            "session_id": "minimal",
            "video_id": "vid",
            "mode": "single_player",
            "status": "completed",
            "results": {
                "players": [
                    {
                        "player_id": "1",
                        "total_distance_km": 0.0,
                        "max_speed_kmh": 0.0,
                        "avg_speed_kmh": 0.0,
                        "sprint_count": 0,
                        "sprints": [],
                        "route": [{"x": 0, "y": 0, "timestamp": 0, "speed": 0}],
                    }
                ],
            },
        }
        result = pdf_service.generate_report(session_data)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
