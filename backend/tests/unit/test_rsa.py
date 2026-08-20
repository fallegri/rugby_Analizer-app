"""Unit tests for RSA (Repeated Sprint Ability) computation."""

import pytest

from src.cv.analytics import AnalyticsEngine, RSAResult, SprintSegment


class TestComputeRSA:
    """Tests for AnalyticsEngine.compute_rsa() method."""

    def test_empty_sprints(self):
        """Test RSA with no sprints returns empty result."""
        engine = AnalyticsEngine(fps=30.0)
        result = engine.compute_rsa([])
        assert result.repeated_sprint_count == 0
        assert result.avg_recovery_time_s == 0.0
        assert result.sprint_clusters == []

    def test_single_sprint(self):
        """Test RSA with a single sprint returns empty result."""
        engine = AnalyticsEngine(fps=30.0)
        sprints = [
            SprintSegment(
                start_frame=0,
                end_frame=30,
                start_position=(0.0, 0.0),
                end_position=(10.0, 0.0),
                max_speed_kmh=25.0,
                distance_m=10.0,
            )
        ]
        result = engine.compute_rsa(sprints)
        assert result.repeated_sprint_count == 0
        assert result.sprint_clusters == []

    def test_two_sprints_within_window(self):
        """Test RSA with two sprints within 30s window."""
        engine = AnalyticsEngine(fps=30.0)
        # Sprint 1: frames 0-30 (0-1s)
        # Sprint 2: frames 300-330 (10-11s) -> gap = (300-30)/30 = 9s < 30s
        sprints = [
            SprintSegment(
                start_frame=0,
                end_frame=30,
                start_position=(0.0, 0.0),
                end_position=(10.0, 0.0),
                max_speed_kmh=25.0,
                distance_m=10.0,
            ),
            SprintSegment(
                start_frame=300,
                end_frame=330,
                start_position=(20.0, 0.0),
                end_position=(30.0, 0.0),
                max_speed_kmh=22.0,
                distance_m=10.0,
            ),
        ]
        result = engine.compute_rsa(sprints)
        assert result.repeated_sprint_count == 2
        assert len(result.sprint_clusters) == 1
        assert len(result.sprint_clusters[0]) == 2
        # Recovery time = (300-30)/30 = 9.0s
        assert result.avg_recovery_time_s == pytest.approx(9.0, abs=0.1)
        assert result.max_recovery_time_s == pytest.approx(9.0, abs=0.1)
        assert result.min_recovery_time_s == pytest.approx(9.0, abs=0.1)

    def test_two_sprints_outside_window(self):
        """Test RSA with two sprints with gap > 30s (no cluster)."""
        engine = AnalyticsEngine(fps=30.0)
        # Sprint 1: frames 0-30 (0-1s)
        # Sprint 2: frames 1000-1030 (33.3s-34.3s) -> gap = (1000-30)/30 = 32.3s > 30s
        sprints = [
            SprintSegment(
                start_frame=0,
                end_frame=30,
                start_position=(0.0, 0.0),
                end_position=(10.0, 0.0),
                max_speed_kmh=25.0,
                distance_m=10.0,
            ),
            SprintSegment(
                start_frame=1000,
                end_frame=1030,
                start_position=(20.0, 0.0),
                end_position=(30.0, 0.0),
                max_speed_kmh=22.0,
                distance_m=10.0,
            ),
        ]
        result = engine.compute_rsa(sprints)
        assert result.repeated_sprint_count == 0
        assert result.sprint_clusters == []

    def test_three_sprints_one_cluster(self):
        """Test RSA with three sprints forming one cluster."""
        engine = AnalyticsEngine(fps=30.0)
        # Sprint 1: 0-1s, Sprint 2: 10-11s, Sprint 3: 20-21s
        sprints = [
            SprintSegment(
                start_frame=0, end_frame=30,
                start_position=(0.0, 0.0), end_position=(10.0, 0.0),
                max_speed_kmh=28.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=300, end_frame=330,
                start_position=(20.0, 0.0), end_position=(30.0, 0.0),
                max_speed_kmh=26.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=600, end_frame=630,
                start_position=(40.0, 0.0), end_position=(50.0, 0.0),
                max_speed_kmh=24.0, distance_m=10.0,
            ),
        ]
        result = engine.compute_rsa(sprints)
        assert result.repeated_sprint_count == 3
        assert len(result.sprint_clusters) == 1
        assert len(result.sprint_clusters[0]) == 3
        # Recovery times: 9s and 9s
        assert result.avg_recovery_time_s == pytest.approx(9.0, abs=0.1)

    def test_speed_degradation(self):
        """Test speed degradation calculation."""
        engine = AnalyticsEngine(fps=30.0)
        # First sprint: 30 km/h, Last sprint: 24 km/h
        # Degradation = (30-24)/30 * 100 = 20%
        sprints = [
            SprintSegment(
                start_frame=0, end_frame=30,
                start_position=(0.0, 0.0), end_position=(10.0, 0.0),
                max_speed_kmh=30.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=300, end_frame=330,
                start_position=(20.0, 0.0), end_position=(30.0, 0.0),
                max_speed_kmh=24.0, distance_m=10.0,
            ),
        ]
        result = engine.compute_rsa(sprints)
        assert result.speed_degradation_percent == pytest.approx(20.0, abs=0.1)

    def test_multiple_clusters(self):
        """Test RSA with multiple distinct clusters."""
        engine = AnalyticsEngine(fps=30.0)
        # Cluster 1: Sprint 0-1s and Sprint 10-11s (gap 9s)
        # Gap between clusters: Sprint 60-61s (gap 49s > 30s)
        # Cluster 2: Sprint 60-61s and Sprint 70-71s (gap 9s)
        sprints = [
            SprintSegment(
                start_frame=0, end_frame=30,
                start_position=(0.0, 0.0), end_position=(10.0, 0.0),
                max_speed_kmh=28.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=300, end_frame=330,
                start_position=(20.0, 0.0), end_position=(30.0, 0.0),
                max_speed_kmh=26.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=1800, end_frame=1830,
                start_position=(40.0, 0.0), end_position=(50.0, 0.0),
                max_speed_kmh=27.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=2100, end_frame=2130,
                start_position=(60.0, 0.0), end_position=(70.0, 0.0),
                max_speed_kmh=25.0, distance_m=10.0,
            ),
        ]
        result = engine.compute_rsa(sprints)
        assert result.repeated_sprint_count == 4
        assert len(result.sprint_clusters) == 2

    def test_custom_window(self):
        """Test RSA with custom window_seconds parameter."""
        engine = AnalyticsEngine(fps=30.0)
        # Gap of 15s: within default 30s window but outside a 10s window
        sprints = [
            SprintSegment(
                start_frame=0, end_frame=30,
                start_position=(0.0, 0.0), end_position=(10.0, 0.0),
                max_speed_kmh=25.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=480, end_frame=510,
                start_position=(20.0, 0.0), end_position=(30.0, 0.0),
                max_speed_kmh=23.0, distance_m=10.0,
            ),
        ]
        # With default 30s window -> cluster
        result_30 = engine.compute_rsa(sprints, window_seconds=30.0)
        assert result_30.repeated_sprint_count == 2

        # With 10s window -> no cluster (gap = (480-30)/30 = 15s > 10s)
        result_10 = engine.compute_rsa(sprints, window_seconds=10.0)
        assert result_10.repeated_sprint_count == 0

    def test_custom_fps(self):
        """Test RSA with custom fps parameter overriding engine fps."""
        engine = AnalyticsEngine(fps=30.0)
        # At 60fps: gap = (300-30)/60 = 4.5s < 30s -> cluster
        sprints = [
            SprintSegment(
                start_frame=0, end_frame=30,
                start_position=(0.0, 0.0), end_position=(10.0, 0.0),
                max_speed_kmh=25.0, distance_m=10.0,
            ),
            SprintSegment(
                start_frame=300, end_frame=330,
                start_position=(20.0, 0.0), end_position=(30.0, 0.0),
                max_speed_kmh=22.0, distance_m=10.0,
            ),
        ]
        result = engine.compute_rsa(sprints, fps=60.0)
        assert result.repeated_sprint_count == 2
        # Recovery time at 60fps = (300-30)/60 = 4.5s
        assert result.avg_recovery_time_s == pytest.approx(4.5, abs=0.1)

    def test_result_dataclass_fields(self):
        """Test that RSAResult has all expected fields."""
        result = RSAResult()
        assert hasattr(result, 'repeated_sprint_count')
        assert hasattr(result, 'avg_recovery_time_s')
        assert hasattr(result, 'max_recovery_time_s')
        assert hasattr(result, 'min_recovery_time_s')
        assert hasattr(result, 'speed_degradation_percent')
        assert hasattr(result, 'sprint_clusters')
