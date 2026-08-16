"""Unit tests for core domain models."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from src.core.enums import AnalysisStatus, TrackingMode, VideoStatus
from src.core.models import (
    AnalysisRequest,
    FieldCalibration,
    PlayerSelection,
    TrackingResult,
    TrackingSession,
    Video,
)


class TestVideo:
    """Tests for the Video model."""

    def test_create_video_minimal(self):
        """Test creating a video with minimal fields."""
        video = Video(filename="test_match.mp4")
        assert video.filename == "test_match.mp4"
        assert video.status == VideoStatus.UPLOADED
        assert isinstance(video.id, UUID)
        assert video.duration is None
        assert video.resolution is None

    def test_create_video_full(self):
        """Test creating a video with all fields."""
        video = Video(
            filename="test_match.mp4",
            status=VideoStatus.ANALYZING,
            duration=3600.0,
            resolution=(1920, 1080),
            fps=30.0,
            file_path="/uploads/test_match.mp4",
        )
        assert video.duration == 3600.0
        assert video.resolution == (1920, 1080)
        assert video.fps == 30.0
        assert video.status == VideoStatus.ANALYZING

    def test_video_status_transitions(self):
        """Test that video status values are valid."""
        for status in VideoStatus:
            video = Video(filename="test.mp4", status=status)
            assert video.status == status


class TestPlayerSelection:
    """Tests for the PlayerSelection model."""

    def test_create_player_selection(self):
        """Test creating a player selection."""
        player = PlayerSelection(
            player_id="player_1",
            bounding_box=(100.0, 200.0, 50.0, 80.0),
            team="team_a",
        )
        assert player.player_id == "player_1"
        assert player.bounding_box == (100.0, 200.0, 50.0, 80.0)
        assert player.team == "team_a"

    def test_player_selection_without_optional_fields(self):
        """Test creating a player selection without optional fields."""
        player = PlayerSelection(
            player_id="player_2",
            bounding_box=(0.0, 0.0, 100.0, 100.0),
        )
        assert player.team is None
        assert player.label is None


class TestFieldCalibration:
    """Tests for the FieldCalibration model."""

    def test_create_field_calibration_default(self):
        """Test creating a default field calibration."""
        cal = FieldCalibration()
        assert cal.points == []
        assert cal.homography_matrix is None
        assert cal.auto_detected is False

    def test_create_field_calibration_with_points(self):
        """Test creating a calibration with reference points."""
        points = [(0.0, 0.0), (100.0, 0.0), (100.0, 70.0), (0.0, 70.0)]
        cal = FieldCalibration(
            points=points,
            auto_detected=True,
            homography_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )
        assert len(cal.points) == 4
        assert cal.auto_detected is True
        assert cal.homography_matrix is not None


class TestAnalysisRequest:
    """Tests for the AnalysisRequest model."""

    def test_create_analysis_request_minimal(self):
        """Test creating a minimal analysis request."""
        from uuid import uuid4

        video_id = uuid4()
        req = AnalysisRequest(video_id=video_id, mode=TrackingMode.BALL_ONLY)
        assert req.video_id == video_id
        assert req.mode == TrackingMode.BALL_ONLY
        assert req.players == []
        assert req.calibration is None

    def test_create_analysis_request_full(self):
        """Test creating a full analysis request."""
        from uuid import uuid4

        video_id = uuid4()
        players = [
            PlayerSelection(player_id="p1", bounding_box=(10.0, 20.0, 30.0, 40.0)),
            PlayerSelection(player_id="p2", bounding_box=(50.0, 60.0, 30.0, 40.0), team="A"),
        ]
        calibration = FieldCalibration(
            points=[(0.0, 0.0), (100.0, 0.0)],
            auto_detected=False,
        )
        req = AnalysisRequest(
            video_id=video_id,
            mode=TrackingMode.GROUP_TRACKING,
            players=players,
            calibration=calibration,
        )
        assert len(req.players) == 2
        assert req.calibration.auto_detected is False


class TestTrackingResult:
    """Tests for the TrackingResult model."""

    def test_create_empty_result(self):
        """Test creating an empty tracking result."""
        result = TrackingResult()
        assert result.routes == []
        assert result.max_speed is None
        assert result.avg_speed is None
        assert result.total_distance is None
        assert result.positions == []

    def test_create_result_with_data(self):
        """Test creating a tracking result with analysis data."""
        result = TrackingResult(
            routes=[[(0.0, 0.0), (10.0, 5.0), (20.0, 10.0)]],
            max_speed=32.5,
            avg_speed=18.2,
            total_distance=4.8,
            positions=[{"frame": 1, "x": 0.0, "y": 0.0}],
        )
        assert result.max_speed == 32.5
        assert result.avg_speed == 18.2
        assert result.total_distance == 4.8
        assert len(result.routes) == 1


class TestTrackingSession:
    """Tests for the TrackingSession model."""

    def test_create_session_default(self):
        """Test creating a default tracking session."""
        from uuid import uuid4

        video_id = uuid4()
        session = TrackingSession(video_id=video_id, mode=TrackingMode.SINGLE_PLAYER)
        assert session.status == AnalysisStatus.PENDING
        assert session.progress == 0.0
        assert session.result is None
        assert session.error_message is None

    def test_session_progress_validation(self):
        """Test that progress must be between 0 and 100."""
        from uuid import uuid4

        video_id = uuid4()

        with pytest.raises(ValidationError):
            TrackingSession(
                video_id=video_id,
                mode=TrackingMode.BALL_ONLY,
                progress=150.0,
            )

        with pytest.raises(ValidationError):
            TrackingSession(
                video_id=video_id,
                mode=TrackingMode.BALL_ONLY,
                progress=-10.0,
            )

    def test_session_with_result(self):
        """Test creating a completed session with results."""
        from uuid import uuid4

        video_id = uuid4()
        result = TrackingResult(
            max_speed=28.0,
            avg_speed=15.0,
            total_distance=3.2,
        )
        session = TrackingSession(
            video_id=video_id,
            mode=TrackingMode.BALL_CARRIER,
            status=AnalysisStatus.COMPLETED,
            result=result,
            progress=100.0,
            target_players=["player_7"],
        )
        assert session.status == AnalysisStatus.COMPLETED
        assert session.result.max_speed == 28.0
        assert session.target_players == ["player_7"]
