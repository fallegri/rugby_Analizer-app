"""Unit tests for the rugby play detection engine.

Tests each play type detection with synthetic movement data.
"""

import pytest

from src.cv.play_detector import DetectedPlay, PlayDetector


class TestPlayDetectorInstantiation:
    """Tests for PlayDetector class creation."""

    def test_instantiation(self):
        """Test PlayDetector can be instantiated."""
        detector = PlayDetector()
        assert detector is not None

    def test_empty_data(self):
        """Test with empty player data returns no plays."""
        detector = PlayDetector()
        result = detector.detect_plays([])
        assert result == []

    def test_single_player_no_plays(self):
        """Test with single player data returns no multi-player plays."""
        detector = PlayDetector()
        players = [
            {
                "player_id": "1",
                "route": [
                    {"x": 50.0, "y": 35.0, "timestamp": 0.0, "speed": 5.0},
                    {"x": 51.0, "y": 35.0, "timestamp": 1.0, "speed": 5.0},
                    {"x": 52.0, "y": 35.0, "timestamp": 2.0, "speed": 5.0},
                ],
                "total_distance_km": 0.002,
                "max_speed_kmh": 5.0,
                "avg_speed_kmh": 5.0,
                "sprint_count": 0,
                "sprints": [],
            }
        ]
        result = detector.detect_plays(players)
        # Should not detect tackles, scrums, rucks, or lineouts
        non_try_plays = [p for p in result if p.play_type != "try"]
        assert non_try_plays == []


class TestTackleDetection:
    """Tests for tackle detection."""

    def test_tackle_detected_converging_players(self):
        """Test tackle detection with two players converging at high speed."""
        detector = PlayDetector()

        # Player A moving right fast, Player B moving left fast
        # They converge at x=50, y=35 at timestamp=1.0
        players = [
            {
                "player_id": "1",
                "route": [
                    {"x": 45.0, "y": 35.0, "timestamp": 0.0, "speed": 20.0},
                    {"x": 47.5, "y": 35.0, "timestamp": 0.5, "speed": 20.0},
                    {"x": 49.5, "y": 35.0, "timestamp": 1.0, "speed": 20.0},
                ],
                "total_distance_km": 0.0045,
                "max_speed_kmh": 20.0,
                "avg_speed_kmh": 20.0,
                "sprint_count": 1,
                "sprints": [],
            },
            {
                "player_id": "2",
                "route": [
                    {"x": 55.0, "y": 35.0, "timestamp": 0.0, "speed": 18.0},
                    {"x": 52.5, "y": 35.0, "timestamp": 0.5, "speed": 18.0},
                    {"x": 50.5, "y": 35.0, "timestamp": 1.0, "speed": 18.0},
                ],
                "total_distance_km": 0.0045,
                "max_speed_kmh": 18.0,
                "avg_speed_kmh": 18.0,
                "sprint_count": 1,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        tackles = [p for p in result if p.play_type == "tackle"]
        assert len(tackles) >= 1
        tackle = tackles[0]
        assert tackle.confidence > 0
        assert "1" in tackle.players_involved or "2" in tackle.players_involved

    def test_no_tackle_when_slow(self):
        """Test no tackle detected when players are moving slowly."""
        detector = PlayDetector()

        players = [
            {
                "player_id": "1",
                "route": [
                    {"x": 49.0, "y": 35.0, "timestamp": 0.0, "speed": 3.0},
                    {"x": 49.5, "y": 35.0, "timestamp": 0.5, "speed": 3.0},
                    {"x": 50.0, "y": 35.0, "timestamp": 1.0, "speed": 3.0},
                ],
                "total_distance_km": 0.001,
                "max_speed_kmh": 3.0,
                "avg_speed_kmh": 3.0,
                "sprint_count": 0,
                "sprints": [],
            },
            {
                "player_id": "2",
                "route": [
                    {"x": 51.0, "y": 35.0, "timestamp": 0.0, "speed": 3.0},
                    {"x": 50.5, "y": 35.0, "timestamp": 0.5, "speed": 3.0},
                    {"x": 50.0, "y": 35.0, "timestamp": 1.0, "speed": 3.0},
                ],
                "total_distance_km": 0.001,
                "max_speed_kmh": 3.0,
                "avg_speed_kmh": 3.0,
                "sprint_count": 0,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        tackles = [p for p in result if p.play_type == "tackle"]
        assert len(tackles) == 0

    def test_no_tackle_when_far_apart(self):
        """Test no tackle when players are far apart despite high speed."""
        detector = PlayDetector()

        players = [
            {
                "player_id": "1",
                "route": [
                    {"x": 10.0, "y": 35.0, "timestamp": 0.0, "speed": 25.0},
                    {"x": 15.0, "y": 35.0, "timestamp": 0.5, "speed": 25.0},
                    {"x": 20.0, "y": 35.0, "timestamp": 1.0, "speed": 25.0},
                ],
                "total_distance_km": 0.01,
                "max_speed_kmh": 25.0,
                "avg_speed_kmh": 25.0,
                "sprint_count": 1,
                "sprints": [],
            },
            {
                "player_id": "2",
                "route": [
                    {"x": 80.0, "y": 35.0, "timestamp": 0.0, "speed": 25.0},
                    {"x": 85.0, "y": 35.0, "timestamp": 0.5, "speed": 25.0},
                    {"x": 90.0, "y": 35.0, "timestamp": 1.0, "speed": 25.0},
                ],
                "total_distance_km": 0.01,
                "max_speed_kmh": 25.0,
                "avg_speed_kmh": 25.0,
                "sprint_count": 1,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        tackles = [p for p in result if p.play_type == "tackle"]
        assert len(tackles) == 0


class TestScrumDetection:
    """Tests for scrum detection."""

    def test_scrum_detected_eight_players_clustered(self):
        """Test scrum detection with 8 players clustered at low speed."""
        detector = PlayDetector()

        # Create 8 players clustered around (50, 35) with low speed for 4 seconds
        players = []
        for i in range(8):
            angle = (i / 8.0) * 2 * 3.14159
            x_offset = 2.0 * (0.5 - (i % 3) * 0.3)
            y_offset = 2.0 * (0.5 - (i % 4) * 0.3)
            route = []
            for t_idx in range(9):  # 0.0 to 4.0 seconds, every 0.5s
                t = t_idx * 0.5
                route.append({
                    "x": 50.0 + x_offset + (t_idx * 0.1),
                    "y": 35.0 + y_offset + (t_idx * 0.05),
                    "timestamp": t,
                    "speed": 1.5,  # Low speed
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.001,
                "max_speed_kmh": 2.0,
                "avg_speed_kmh": 1.5,
                "sprint_count": 0,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        scrums = [p for p in result if p.play_type == "scrum"]
        assert len(scrums) >= 1
        scrum = scrums[0]
        assert scrum.confidence > 0
        assert len(scrum.players_involved) >= 8

    def test_no_scrum_with_fewer_than_eight_players(self):
        """Test no scrum with only 5 clustered players."""
        detector = PlayDetector()

        players = []
        for i in range(5):
            route = []
            for t_idx in range(9):
                t = t_idx * 0.5
                route.append({
                    "x": 50.0 + (i * 0.5),
                    "y": 35.0 + (i * 0.3),
                    "timestamp": t,
                    "speed": 1.0,
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.001,
                "max_speed_kmh": 1.5,
                "avg_speed_kmh": 1.0,
                "sprint_count": 0,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        scrums = [p for p in result if p.play_type == "scrum"]
        assert len(scrums) == 0


class TestRuckDetection:
    """Tests for ruck detection."""

    def test_ruck_detected_four_players_clustered(self):
        """Test ruck detection with 4 players clustered at low speed."""
        detector = PlayDetector()

        # Create 4 players clustered within 3m, low speed, for 3 seconds
        players = []
        for i in range(4):
            route = []
            for t_idx in range(7):  # 0 to 3.0s at 0.5s intervals
                t = t_idx * 0.5
                route.append({
                    "x": 50.0 + (i * 0.5),
                    "y": 35.0 + (i * 0.4),
                    "timestamp": t,
                    "speed": 1.0,
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.001,
                "max_speed_kmh": 1.5,
                "avg_speed_kmh": 1.0,
                "sprint_count": 0,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        rucks = [p for p in result if p.play_type == "ruck"]
        assert len(rucks) >= 1
        ruck = rucks[0]
        assert ruck.confidence > 0
        assert len(ruck.players_involved) >= 3

    def test_no_ruck_with_high_speed(self):
        """Test no ruck when players are moving at high speed."""
        detector = PlayDetector()

        players = []
        for i in range(4):
            route = []
            for t_idx in range(7):
                t = t_idx * 0.5
                route.append({
                    "x": 50.0 + (i * 0.5) + (t_idx * 5),
                    "y": 35.0 + (i * 0.4),
                    "timestamp": t,
                    "speed": 20.0,  # High speed
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.015,
                "max_speed_kmh": 20.0,
                "avg_speed_kmh": 20.0,
                "sprint_count": 1,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        rucks = [p for p in result if p.play_type == "ruck"]
        assert len(rucks) == 0


class TestTryDetection:
    """Tests for try detection."""

    def test_try_detected_crossing_high_line(self):
        """Test try detection when player crosses x=95m at speed."""
        detector = PlayDetector()

        players = [
            {
                "player_id": "9",
                "route": [
                    {"x": 90.0, "y": 35.0, "timestamp": 0.0, "speed": 25.0},
                    {"x": 93.0, "y": 35.0, "timestamp": 1.0, "speed": 25.0},
                    {"x": 96.0, "y": 35.0, "timestamp": 2.0, "speed": 25.0},
                ],
                "total_distance_km": 0.006,
                "max_speed_kmh": 25.0,
                "avg_speed_kmh": 25.0,
                "sprint_count": 1,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        trys = [p for p in result if p.play_type == "try"]
        assert len(trys) == 1
        assert trys[0].players_involved == ["9"]
        assert trys[0].confidence > 0.5

    def test_try_detected_crossing_low_line(self):
        """Test try detection when player crosses x=5m at speed (other direction)."""
        detector = PlayDetector()

        players = [
            {
                "player_id": "7",
                "route": [
                    {"x": 10.0, "y": 20.0, "timestamp": 0.0, "speed": 18.0},
                    {"x": 7.0, "y": 20.0, "timestamp": 1.0, "speed": 18.0},
                    {"x": 4.0, "y": 20.0, "timestamp": 2.0, "speed": 18.0},
                ],
                "total_distance_km": 0.006,
                "max_speed_kmh": 18.0,
                "avg_speed_kmh": 18.0,
                "sprint_count": 1,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        trys = [p for p in result if p.play_type == "try"]
        assert len(trys) == 1
        assert trys[0].players_involved == ["7"]

    def test_no_try_when_slow(self):
        """Test no try when player crosses line but at low speed."""
        detector = PlayDetector()

        players = [
            {
                "player_id": "5",
                "route": [
                    {"x": 93.0, "y": 35.0, "timestamp": 0.0, "speed": 3.0},
                    {"x": 94.0, "y": 35.0, "timestamp": 1.0, "speed": 3.0},
                    {"x": 96.0, "y": 35.0, "timestamp": 2.0, "speed": 3.0},
                ],
                "total_distance_km": 0.003,
                "max_speed_kmh": 3.0,
                "avg_speed_kmh": 3.0,
                "sprint_count": 0,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        trys = [p for p in result if p.play_type == "try"]
        assert len(trys) == 0

    def test_no_try_without_crossing(self):
        """Test no try when player is near but doesn't cross the line."""
        detector = PlayDetector()

        players = [
            {
                "player_id": "3",
                "route": [
                    {"x": 90.0, "y": 35.0, "timestamp": 0.0, "speed": 25.0},
                    {"x": 92.0, "y": 35.0, "timestamp": 1.0, "speed": 25.0},
                    {"x": 94.0, "y": 35.0, "timestamp": 2.0, "speed": 25.0},
                ],
                "total_distance_km": 0.004,
                "max_speed_kmh": 25.0,
                "avg_speed_kmh": 25.0,
                "sprint_count": 1,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        trys = [p for p in result if p.play_type == "try"]
        assert len(trys) == 0


class TestLineoutDetection:
    """Tests for line-out detection."""

    def test_lineout_detected_near_sideline(self):
        """Test line-out detection with 4+ players near sideline."""
        detector = PlayDetector()

        # Create 5 players near the low sideline (y < 5) at low speed
        players = []
        for i in range(5):
            route = []
            for t_idx in range(7):  # 0 to 3.0s
                t = t_idx * 0.5
                route.append({
                    "x": 30.0 + (i * 1.5),
                    "y": 3.0 + (i * 0.3),  # All near y < 5
                    "timestamp": t,
                    "speed": 1.0,
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.001,
                "max_speed_kmh": 1.5,
                "avg_speed_kmh": 1.0,
                "sprint_count": 0,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        lineouts = [p for p in result if p.play_type == "lineout"]
        assert len(lineouts) >= 1
        lineout = lineouts[0]
        assert len(lineout.players_involved) >= 4

    def test_lineout_detected_near_high_sideline(self):
        """Test line-out detection near y > 63m sideline."""
        detector = PlayDetector()

        players = []
        for i in range(4):
            route = []
            for t_idx in range(7):
                t = t_idx * 0.5
                route.append({
                    "x": 40.0 + (i * 1.0),
                    "y": 64.0 + (i * 0.2),  # All near y > 63
                    "timestamp": t,
                    "speed": 2.0,
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.001,
                "max_speed_kmh": 2.0,
                "avg_speed_kmh": 2.0,
                "sprint_count": 0,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        lineouts = [p for p in result if p.play_type == "lineout"]
        assert len(lineouts) >= 1

    def test_no_lineout_in_center(self):
        """Test no line-out for players in center of field."""
        detector = PlayDetector()

        players = []
        for i in range(5):
            route = []
            for t_idx in range(7):
                t = t_idx * 0.5
                route.append({
                    "x": 50.0 + (i * 1.5),
                    "y": 35.0,  # Center of field
                    "timestamp": t,
                    "speed": 1.0,
                })
            players.append({
                "player_id": str(i + 1),
                "route": route,
                "total_distance_km": 0.001,
                "max_speed_kmh": 1.5,
                "avg_speed_kmh": 1.0,
                "sprint_count": 0,
                "sprints": [],
            })

        result = detector.detect_plays(players)
        lineouts = [p for p in result if p.play_type == "lineout"]
        assert len(lineouts) == 0


class TestNoFalsePositives:
    """Test that normal movement doesn't trigger false positives."""

    def test_normal_movement_no_plays(self):
        """Test that players moving at normal pace across the field don't trigger plays."""
        detector = PlayDetector()

        # Two players running at moderate speed, spread out
        players = [
            {
                "player_id": "1",
                "route": [
                    {"x": 20.0, "y": 30.0, "timestamp": 0.0, "speed": 10.0},
                    {"x": 22.0, "y": 30.5, "timestamp": 1.0, "speed": 10.0},
                    {"x": 24.0, "y": 31.0, "timestamp": 2.0, "speed": 10.0},
                    {"x": 26.0, "y": 31.5, "timestamp": 3.0, "speed": 10.0},
                    {"x": 28.0, "y": 32.0, "timestamp": 4.0, "speed": 10.0},
                ],
                "total_distance_km": 0.008,
                "max_speed_kmh": 10.0,
                "avg_speed_kmh": 10.0,
                "sprint_count": 0,
                "sprints": [],
            },
            {
                "player_id": "2",
                "route": [
                    {"x": 60.0, "y": 40.0, "timestamp": 0.0, "speed": 8.0},
                    {"x": 62.0, "y": 40.5, "timestamp": 1.0, "speed": 8.0},
                    {"x": 64.0, "y": 41.0, "timestamp": 2.0, "speed": 8.0},
                    {"x": 66.0, "y": 41.5, "timestamp": 3.0, "speed": 8.0},
                    {"x": 68.0, "y": 42.0, "timestamp": 4.0, "speed": 8.0},
                ],
                "total_distance_km": 0.008,
                "max_speed_kmh": 8.0,
                "avg_speed_kmh": 8.0,
                "sprint_count": 0,
                "sprints": [],
            },
        ]

        result = detector.detect_plays(players)
        assert len(result) == 0


class TestDetectedPlayDataclass:
    """Tests for the DetectedPlay dataclass."""

    def test_detected_play_fields(self):
        """Test DetectedPlay has all expected fields."""
        play = DetectedPlay(
            play_type="tackle",
            start_time=1.0,
            end_time=1.5,
            confidence=0.85,
            players_involved=["1", "2"],
            position=(50.0, 35.0),
            description="Test tackle",
        )
        assert play.play_type == "tackle"
        assert play.start_time == 1.0
        assert play.end_time == 1.5
        assert play.confidence == 0.85
        assert play.players_involved == ["1", "2"]
        assert play.position == (50.0, 35.0)
        assert play.description == "Test tackle"
        assert play.ai_explanation is None

    def test_detected_play_with_ai_explanation(self):
        """Test DetectedPlay with ai_explanation set."""
        play = DetectedPlay(
            play_type="try",
            start_time=5.0,
            end_time=5.5,
            confidence=0.95,
            players_involved=["9"],
            position=(96.0, 35.0),
            description="Try scored",
            ai_explanation="This is a confirmed try scoring movement.",
        )
        assert play.ai_explanation == "This is a confirmed try scoring movement."
