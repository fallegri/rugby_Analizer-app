"""Unit tests for tracking mode strategies.

Tests each strategy filtering behavior with known track configurations.
"""

import numpy as np
import pytest

from src.cv.detector import Detection
from src.cv.tracker import Track
from src.cv.tracking_modes import (
    BallCarrierStrategy,
    BallOnlyStrategy,
    FilteredResult,
    GroupTrackingStrategy,
    SinglePlayerStrategy,
    TrackingStrategy,
)


def _make_track(
    track_id: int,
    bbox: tuple[float, float, float, float],
    class_id: int = 0,
    confidence: float = 0.9,
) -> Track:
    """Helper to create a Track with given parameters."""
    return Track(
        id=track_id,
        bbox=bbox,
        class_id=class_id,
        confidence=confidence,
        history=[],
    )


class TestSinglePlayerStrategy:
    """Tests for SinglePlayerStrategy."""

    def test_filters_to_target_id(self):
        """Test that only the target track is returned."""
        strategy = SinglePlayerStrategy()
        tracks = [
            _make_track(1, (10, 10, 50, 50)),
            _make_track(2, (100, 100, 150, 150)),
            _make_track(3, (200, 200, 250, 250)),
        ]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = strategy.process_frame(frame, [], tracks, target_ids=[2])

        assert len(result.tracks) == 1
        assert result.tracks[0].id == 2
        assert result.primary_track_id == 2

    def test_returns_empty_when_target_not_found(self):
        """Test returns empty when target ID is not in tracks."""
        strategy = SinglePlayerStrategy()
        tracks = [
            _make_track(1, (10, 10, 50, 50)),
            _make_track(2, (100, 100, 150, 150)),
        ]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = strategy.process_frame(frame, [], tracks, target_ids=[99])

        assert len(result.tracks) == 0
        assert result.primary_track_id is None

    def test_returns_empty_when_no_target_ids(self):
        """Test returns empty when no target IDs specified."""
        strategy = SinglePlayerStrategy()
        tracks = [_make_track(1, (10, 10, 50, 50))]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = strategy.process_frame(frame, [], tracks, target_ids=None)

        assert len(result.tracks) == 0

    def test_uses_first_target_id_only(self):
        """Test that only the first target ID is used."""
        strategy = SinglePlayerStrategy()
        tracks = [
            _make_track(1, (10, 10, 50, 50)),
            _make_track(2, (100, 100, 150, 150)),
        ]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = strategy.process_frame(frame, [], tracks, target_ids=[1, 2])

        assert len(result.tracks) == 1
        assert result.tracks[0].id == 1


class TestBallCarrierStrategy:
    """Tests for BallCarrierStrategy."""

    def test_finds_nearest_player_to_ball(self):
        """Test that the player nearest to the ball is identified."""
        strategy = BallCarrierStrategy()

        ball_track = _make_track(10, (45, 45, 55, 55), class_id=32, confidence=0.9)
        player1 = _make_track(1, (40, 40, 60, 60), class_id=0, confidence=0.9)
        player2 = _make_track(2, (200, 200, 250, 250), class_id=0, confidence=0.9)

        tracks = [player1, player2, ball_track]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)

        assert result.primary_track_id == 1
        assert result.ball_track_id == 10
        assert len(result.tracks) == 1
        assert result.tracks[0].id == 1

    def test_returns_empty_when_no_ball(self):
        """Test behavior when no ball is detected."""
        strategy = BallCarrierStrategy()

        tracks = [
            _make_track(1, (10, 10, 50, 50), class_id=0),
            _make_track(2, (100, 100, 150, 150), class_id=0),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)
        assert len(result.tracks) <= 1

    def test_returns_empty_when_no_players(self):
        """Test behavior when no players are detected (only ball)."""
        strategy = BallCarrierStrategy()

        tracks = [_make_track(10, (50, 50, 60, 60), class_id=32)]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)
        assert result.primary_track_id is None

    def test_switches_carrier_when_ball_moves(self):
        """Test that carrier switches when ball moves to another player."""
        strategy = BallCarrierStrategy()

        ball = _make_track(10, (195, 195, 205, 205), class_id=32)
        player1 = _make_track(1, (10, 10, 50, 50), class_id=0)
        player2 = _make_track(2, (180, 180, 220, 220), class_id=0)

        tracks = [player1, player2, ball]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)
        assert result.primary_track_id == 2


class TestBallOnlyStrategy:
    """Tests for BallOnlyStrategy."""

    def test_filters_to_ball_only(self):
        """Test that only ball tracks are returned."""
        strategy = BallOnlyStrategy()

        tracks = [
            _make_track(1, (10, 10, 50, 50), class_id=0),
            _make_track(2, (100, 100, 150, 150), class_id=0),
            _make_track(10, (200, 200, 220, 220), class_id=32),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)

        assert len(result.tracks) == 1
        assert result.tracks[0].id == 10
        assert result.tracks[0].class_id == 32
        assert result.primary_track_id == 10
        assert result.ball_track_id == 10

    def test_returns_empty_when_no_ball(self):
        """Test returns empty when no ball is in tracks."""
        strategy = BallOnlyStrategy()

        tracks = [
            _make_track(1, (10, 10, 50, 50), class_id=0),
            _make_track(2, (100, 100, 150, 150), class_id=0),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)
        assert len(result.tracks) == 0
        assert result.primary_track_id is None

    def test_multiple_ball_tracks(self):
        """Test behavior with multiple ball detections."""
        strategy = BallOnlyStrategy()

        tracks = [
            _make_track(10, (50, 50, 60, 60), class_id=32, confidence=0.7),
            _make_track(11, (100, 100, 110, 110), class_id=32, confidence=0.9),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks)
        assert len(result.tracks) == 2
        assert result.primary_track_id == 11


class TestGroupTrackingStrategy:
    """Tests for GroupTrackingStrategy."""

    def test_filters_to_target_group(self):
        """Test that only tracks in the target group are returned."""
        strategy = GroupTrackingStrategy()

        tracks = [
            _make_track(1, (10, 10, 50, 50)),
            _make_track(2, (100, 100, 150, 150)),
            _make_track(3, (200, 200, 250, 250)),
            _make_track(4, (300, 300, 350, 350)),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks, target_ids=[1, 3, 4])

        assert len(result.tracks) == 3
        track_ids = {t.id for t in result.tracks}
        assert track_ids == {1, 3, 4}

    def test_returns_empty_when_no_target_ids(self):
        """Test returns empty when no target IDs."""
        strategy = GroupTrackingStrategy()

        tracks = [_make_track(1, (10, 10, 50, 50))]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks, target_ids=None)
        assert len(result.tracks) == 0

    def test_returns_empty_for_empty_target_list(self):
        """Test returns empty for empty target list."""
        strategy = GroupTrackingStrategy()

        tracks = [_make_track(1, (10, 10, 50, 50))]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks, target_ids=[])
        assert len(result.tracks) == 0

    def test_partial_match(self):
        """Test when only some target IDs exist in tracks."""
        strategy = GroupTrackingStrategy()

        tracks = [
            _make_track(1, (10, 10, 50, 50)),
            _make_track(2, (100, 100, 150, 150)),
        ]
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        result = strategy.process_frame(frame, [], tracks, target_ids=[1, 5, 10])

        assert len(result.tracks) == 1
        assert result.tracks[0].id == 1


class TestTrackingStrategyBase:
    """Tests for base TrackingStrategy ABC."""

    def test_cannot_instantiate_abstract(self):
        """Test that TrackingStrategy cannot be directly instantiated."""
        with pytest.raises(TypeError):
            TrackingStrategy()
