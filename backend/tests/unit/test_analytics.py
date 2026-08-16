"""Unit tests for the analytics engine.

Uses known trajectories to verify distance, speed, and sprint calculations.
"""

import math

import pytest

from src.cv.analytics import AnalyticsEngine, AnalyticsResult, SprintSegment


class TestAnalyticsEngine:
    """Tests for AnalyticsEngine class."""

    def test_instantiation(self):
        """Test engine can be instantiated with defaults."""
        engine = AnalyticsEngine(fps=30.0)
        assert engine.fps == 30.0
        assert engine.sprint_threshold_kmh == 20.0

    def test_invalid_fps_raises(self):
        """Test that zero or negative FPS raises ValueError."""
        with pytest.raises(ValueError, match="FPS must be positive"):
            AnalyticsEngine(fps=0)
        with pytest.raises(ValueError, match="FPS must be positive"):
            AnalyticsEngine(fps=-10)

    def test_single_point(self):
        """Test with single point returns zero metrics."""
        engine = AnalyticsEngine(fps=30.0)
        result = engine.compute([(50.0, 35.0, 0)])
        assert result.total_distance_km == 0.0
        assert result.max_speed_kmh == 0.0
        assert result.avg_speed_kmh == 0.0
        assert len(result.sprint_segments) == 0

    def test_empty_positions(self):
        """Test with empty positions returns zero metrics."""
        engine = AnalyticsEngine(fps=30.0)
        result = engine.compute([])
        assert result.total_distance_km == 0.0

    def test_known_distance_100m(self):
        """Test total distance for a straight 100m run."""
        engine = AnalyticsEngine(fps=30.0)

        positions = [(float(i * 10), 35.0, i * 30) for i in range(11)]

        result = engine.compute(positions)
        assert result.total_distance_km == pytest.approx(0.1, abs=0.001)

    def test_known_speed_100m_in_10s(self):
        """Test speed calculation: 100m in 10s = 36 km/h."""
        engine = AnalyticsEngine(fps=30.0, speed_window=1)

        positions = [(float(i * 10), 35.0, i * 30) for i in range(11)]

        result = engine.compute(positions)
        assert result.avg_speed_kmh == pytest.approx(36.0, abs=0.1)
        assert result.max_speed_kmh == pytest.approx(36.0, abs=0.1)

    def test_varying_speeds(self):
        """Test with varying speeds (acceleration then deceleration)."""
        engine = AnalyticsEngine(fps=30.0, speed_window=1)

        positions = [
            (0.0, 35.0, 0),
            (5.0, 35.0, 30),
            (15.0, 35.0, 60),
            (20.0, 35.0, 90),
        ]

        result = engine.compute(positions)
        assert result.total_distance_km == pytest.approx(0.02, abs=0.001)
        assert result.max_speed_kmh == pytest.approx(36.0, abs=0.1)
        assert result.avg_speed_kmh == pytest.approx(24.0, abs=0.1)

    def test_diagonal_movement(self):
        """Test distance calculation with diagonal movement."""
        engine = AnalyticsEngine(fps=30.0, speed_window=1)

        positions = [
            (0.0, 0.0, 0),
            (30.0, 40.0, 30),
        ]

        result = engine.compute(positions)
        assert result.total_distance_km == pytest.approx(0.05, abs=0.001)
        assert result.max_speed_kmh == pytest.approx(180.0, abs=0.1)

    def test_sprint_detection(self):
        """Test sprint segment detection with known trajectory."""
        engine = AnalyticsEngine(
            fps=30.0,
            sprint_threshold_kmh=20.0,
            speed_window=1,
        )

        positions = [
            (0.0, 35.0, 0),
            (3.0, 35.0, 30),
            (11.0, 35.0, 60),
            (20.0, 35.0, 90),
            (22.0, 35.0, 120),
        ]

        result = engine.compute(positions)
        assert len(result.sprint_segments) == 1
        sprint = result.sprint_segments[0]
        assert sprint.start_frame == 30
        assert sprint.max_speed_kmh == pytest.approx(32.4, abs=0.1)

    def test_route_points_include_timestamps(self):
        """Test that route points include correct timestamps."""
        engine = AnalyticsEngine(fps=30.0)

        positions = [
            (0.0, 0.0, 0),
            (10.0, 0.0, 30),
            (20.0, 0.0, 60),
        ]

        result = engine.compute(positions)
        assert len(result.route_points) == 3
        assert result.route_points[0] == (0.0, 0.0, 0.0)
        assert result.route_points[1] == (10.0, 0.0, 1.0)
        assert result.route_points[2] == (20.0, 0.0, 2.0)

    def test_speed_window_averaging(self):
        """Test that speed window properly averages for max speed."""
        engine = AnalyticsEngine(fps=30.0, speed_window=3)

        positions = [
            (0.0, 35.0, 0),
            (5.0, 35.0, 30),
            (20.0, 35.0, 60),
            (25.0, 35.0, 90),
            (30.0, 35.0, 120),
        ]

        result = engine.compute(positions)
        assert result.max_speed_kmh == pytest.approx(30.0, abs=0.1)

    def test_total_distance_circular_path(self):
        """Test distance for a roughly circular path."""
        engine = AnalyticsEngine(fps=30.0)

        positions = [
            (0.0, 0.0, 0),
            (10.0, 0.0, 30),
            (10.0, 10.0, 60),
            (0.0, 10.0, 90),
            (0.0, 0.0, 120),
        ]

        result = engine.compute(positions)
        assert result.total_distance_km == pytest.approx(0.04, abs=0.001)
