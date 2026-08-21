"""Unit tests for the TeamClassifier module.

Tests team classification by dominant jersey color using synthetic images.
"""

import numpy as np
import pytest

from src.cv.team_classifier import TeamClassifier


class TestGetDominantColor:
    """Tests for the _get_dominant_color helper method."""

    def test_solid_red_patch(self):
        """A solid red patch should return approximately red."""
        classifier = TeamClassifier()
        # Create a 40x40 solid red image (BGR format)
        red_image = np.zeros((40, 40, 3), dtype=np.uint8)
        red_image[:, :] = [0, 0, 255]  # BGR: blue=0, green=0, red=255

        color = classifier._get_dominant_color(red_image)
        assert color is not None
        r, g, b = color
        # Should be mostly red
        assert r > 200
        assert g < 50
        assert b < 50

    def test_solid_blue_patch(self):
        """A solid blue patch should return approximately blue."""
        classifier = TeamClassifier()
        # Create a 40x40 solid blue image (BGR format)
        blue_image = np.zeros((40, 40, 3), dtype=np.uint8)
        blue_image[:, :] = [255, 0, 0]  # BGR: blue=255, green=0, red=0

        color = classifier._get_dominant_color(blue_image)
        assert color is not None
        r, g, b = color
        # Should be mostly blue
        assert b > 200
        assert r < 50
        assert g < 50

    def test_ignores_green_field(self):
        """Green (field) pixels should be filtered out, returning non-green color."""
        classifier = TeamClassifier()
        # Create an image with 80% green (field) and 20% red (jersey)
        image = np.zeros((40, 40, 3), dtype=np.uint8)
        image[:32, :] = [0, 180, 0]  # BGR green (field) - top 80%
        image[32:, :] = [0, 0, 255]  # BGR red (jersey) - bottom 20%

        color = classifier._get_dominant_color(image)
        assert color is not None
        r, g, b = color
        # Should return the red color, not the green
        assert r > 100
        # Green should not dominate
        assert r > g or b > g

    def test_empty_crop_returns_none(self):
        """An empty image should return None."""
        classifier = TeamClassifier()
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        color = classifier._get_dominant_color(empty)
        assert color is None


class TestClassifyPlayer:
    """Tests for classify_player method."""

    def test_classifies_team_a_correctly(self):
        """A player wearing red should be classified as team_a when team_a is red."""
        classifier = TeamClassifier(
            team_a_color=(255, 0, 0),
            team_b_color=(0, 0, 255),
            auto_detect=False,
        )

        # Create a frame with a red player in a bounding box
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[:, :] = [0, 150, 0]  # Green field background (BGR)
        # Place a red jersey in the bbox area
        frame[10:90, 50:150] = [0, 0, 255]  # BGR red

        bbox = (50, 10, 150, 90)
        result = classifier.classify_player(frame, bbox)
        assert result == "team_a"

    def test_classifies_team_b_correctly(self):
        """A player wearing blue should be classified as team_b when team_b is blue."""
        classifier = TeamClassifier(
            team_a_color=(255, 0, 0),
            team_b_color=(0, 0, 255),
            auto_detect=False,
        )

        # Create a frame with a blue player in a bounding box
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        frame[:, :] = [0, 150, 0]  # Green field background
        # Place a blue jersey in the bbox area
        frame[10:90, 50:150] = [255, 0, 0]  # BGR blue

        bbox = (50, 10, 150, 90)
        result = classifier.classify_player(frame, bbox)
        assert result == "team_b"

    def test_returns_none_when_no_colors_detected(self):
        """Returns None when team colors have not been set or detected."""
        classifier = TeamClassifier(auto_detect=True)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, :] = [0, 0, 200]  # Red player

        bbox = (10, 10, 90, 90)
        result = classifier.classify_player(frame, bbox)
        assert result is None

    def test_returns_none_for_invalid_bbox(self):
        """Returns None for bounding boxes that are zero-area."""
        classifier = TeamClassifier(
            team_a_color=(255, 0, 0),
            team_b_color=(0, 0, 255),
        )

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = (50, 50, 50, 50)  # Zero-area
        result = classifier.classify_player(frame, bbox)
        assert result is None


class TestAutoDetectTeams:
    """Tests for auto_detect_teams method."""

    def test_detects_two_distinct_colors(self):
        """Should identify two distinct team colors from player bounding boxes."""
        classifier = TeamClassifier()

        # Create a frame with two groups of colored players
        frame = np.zeros((400, 400, 3), dtype=np.uint8)
        frame[:, :] = [0, 150, 0]  # Green field

        # Team A players (red jerseys) - top half
        frame[10:60, 10:60] = [0, 0, 255]  # Red (BGR)
        frame[10:60, 70:120] = [0, 0, 240]  # Similar red
        frame[10:60, 130:180] = [0, 0, 250]  # Similar red

        # Team B players (blue jerseys) - bottom half
        frame[200:250, 10:60] = [255, 0, 0]  # Blue (BGR)
        frame[200:250, 70:120] = [240, 0, 0]  # Similar blue
        frame[200:250, 130:180] = [250, 0, 0]  # Similar blue

        bboxes = [
            (10, 10, 60, 60),
            (70, 10, 120, 60),
            (130, 10, 180, 60),
            (10, 200, 60, 250),
            (70, 200, 120, 250),
            (130, 200, 180, 250),
        ]

        team_a, team_b = classifier.auto_detect_teams(frame, bboxes)

        # Should return two distinct colors
        assert team_a is not None
        assert team_b is not None
        assert len(team_a) == 3
        assert len(team_b) == 3

        # The two teams should be distinguishable (large distance between them)
        dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(team_a, team_b)))
        assert dist > 100, f"Team colors should be distinct, got distance={dist}"

    def test_returns_defaults_with_insufficient_data(self):
        """Should return default colors when less than 2 bboxes provide data."""
        classifier = TeamClassifier()

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        bboxes = [(10, 10, 20, 20)]  # Only one bbox

        team_a, team_b = classifier.auto_detect_teams(frame, bboxes)
        # Should return defaults
        assert team_a == (255, 0, 0)
        assert team_b == (0, 0, 255)


class TestCollectDetectionSample:
    """Tests for collect_detection_sample method (progressive auto-detection)."""

    def test_collects_samples_and_detects(self):
        """After enough frames, should auto-detect team colors."""
        classifier = TeamClassifier(auto_detect=True)
        assert not classifier._colors_detected

        # Simulate 5 frames with distinct colored players
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        frame[:, :] = [0, 150, 0]  # Green field

        # Red players on left
        frame[10:60, 10:60] = [0, 0, 255]
        frame[10:60, 70:120] = [0, 0, 250]
        # Blue players on right
        frame[10:60, 200:250] = [255, 0, 0]
        frame[10:60, 260:310] = [240, 0, 0]

        bboxes = [
            (10, 10, 60, 60),
            (70, 10, 120, 60),
            (200, 10, 250, 60),
            (260, 10, 310, 60),
        ]

        # Call collect_detection_sample for 5 frames
        for i in range(5):
            result = classifier.collect_detection_sample(frame, bboxes)

        # After 5 frames it should have detected colors
        assert result is True
        assert classifier._colors_detected
        assert classifier.team_a_color is not None
        assert classifier.team_b_color is not None

    def test_not_detected_with_too_few_frames(self):
        """Should not detect colors with fewer frames than needed."""
        classifier = TeamClassifier(auto_detect=True)

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:, :] = [0, 0, 255]  # Red

        bboxes = [(10, 10, 90, 90)]

        # Only 2 frames
        for _ in range(2):
            result = classifier.collect_detection_sample(frame, bboxes)

        assert result is False
        assert not classifier._colors_detected


class TestIntegration:
    """Integration tests combining multiple TeamClassifier methods."""

    def test_full_workflow_auto_detect_then_classify(self):
        """Full workflow: auto-detect colors, then classify new players."""
        classifier = TeamClassifier(auto_detect=True)

        # Frame with distinct teams
        frame = np.zeros((200, 400, 3), dtype=np.uint8)
        frame[:, :] = [0, 150, 0]  # Green field

        # Red team
        frame[10:60, 10:60] = [0, 0, 255]  # Red (BGR)
        frame[10:60, 70:120] = [0, 0, 255]
        # Blue team
        frame[10:60, 200:250] = [255, 0, 0]  # Blue (BGR)
        frame[10:60, 260:310] = [255, 0, 0]

        bboxes = [
            (10, 10, 60, 60),
            (70, 10, 120, 60),
            (200, 10, 250, 60),
            (260, 10, 310, 60),
        ]

        # Collect samples until detected
        for _ in range(5):
            classifier.collect_detection_sample(frame, bboxes)

        assert classifier._colors_detected

        # Now classify a new red player
        new_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        new_frame[:, :] = [0, 0, 255]  # All red (BGR)
        result = classifier.classify_player(new_frame, (0, 0, 100, 100))
        assert result is not None
        # Should be one of the teams
        assert result in ("team_a", "team_b")
