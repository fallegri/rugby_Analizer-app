"""Unit tests for the multi-object tracker module.

Tests track assignment, ID persistence across frames, and track lifecycle.
"""

import pytest

from src.cv.detector import Detection
from src.cv.tracker import MultiObjectTracker, Track, _iou


class TestIoU:
    """Tests for IoU computation."""

    def test_perfect_overlap(self):
        """Test IoU of identical boxes is 1.0."""
        box = (10.0, 20.0, 50.0, 60.0)
        assert _iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        """Test IoU of non-overlapping boxes is 0.0."""
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (20.0, 20.0, 30.0, 30.0)
        assert _iou(box_a, box_b) == 0.0

    def test_partial_overlap(self):
        """Test IoU with known partial overlap."""
        box_a = (0.0, 0.0, 10.0, 10.0)
        box_b = (5.0, 5.0, 15.0, 15.0)
        expected_iou = 25.0 / 175.0
        assert _iou(box_a, box_b) == pytest.approx(expected_iou, rel=1e-5)

    def test_contained_box(self):
        """Test IoU when one box is inside another."""
        outer = (0.0, 0.0, 100.0, 100.0)
        inner = (25.0, 25.0, 75.0, 75.0)
        expected_iou = 2500.0 / 10000.0
        assert _iou(outer, inner) == pytest.approx(expected_iou, rel=1e-5)


class TestMultiObjectTracker:
    """Tests for MultiObjectTracker class."""

    def test_initialization(self):
        """Test tracker initializes with empty state."""
        tracker = MultiObjectTracker()
        assert tracker.get_track(1) is None

    def test_first_frame_creates_tracks(self):
        """Test that first detections create new tracks."""
        tracker = MultiObjectTracker()
        detections = [
            Detection(bbox=(10, 20, 50, 60), class_id=0, confidence=0.9, class_name="person"),
            Detection(bbox=(100, 200, 150, 250), class_id=0, confidence=0.85, class_name="person"),
        ]

        tracks = tracker.update(detections, frame_num=0)
        assert len(tracks) == 2
        assert tracks[0].id == 1
        assert tracks[1].id == 2

    def test_track_id_persistence(self):
        """Test that track IDs persist across frames with overlapping detections."""
        tracker = MultiObjectTracker(iou_threshold=0.3)

        det_frame0 = [
            Detection(bbox=(100, 100, 200, 200), class_id=0, confidence=0.9, class_name="person"),
            Detection(bbox=(300, 300, 400, 400), class_id=0, confidence=0.85, class_name="person"),
        ]
        tracks0 = tracker.update(det_frame0, frame_num=0)
        id_track1 = tracks0[0].id
        id_track2 = tracks0[1].id

        det_frame1 = [
            Detection(bbox=(105, 105, 205, 205), class_id=0, confidence=0.88, class_name="person"),
            Detection(bbox=(305, 305, 405, 405), class_id=0, confidence=0.82, class_name="person"),
        ]
        tracks1 = tracker.update(det_frame1, frame_num=1)

        assert len(tracks1) == 2
        track_ids = {t.id for t in tracks1}
        assert id_track1 in track_ids
        assert id_track2 in track_ids

    def test_new_track_for_distant_detection(self):
        """Test that a detection far from existing tracks creates a new track."""
        tracker = MultiObjectTracker(iou_threshold=0.3)

        det_frame0 = [
            Detection(bbox=(10, 10, 50, 50), class_id=0, confidence=0.9, class_name="person"),
        ]
        tracks0 = tracker.update(det_frame0, frame_num=0)
        assert len(tracks0) == 1

        det_frame1 = [
            Detection(bbox=(10, 10, 50, 50), class_id=0, confidence=0.9, class_name="person"),
            Detection(bbox=(500, 500, 600, 600), class_id=0, confidence=0.8, class_name="person"),
        ]
        tracks1 = tracker.update(det_frame1, frame_num=1)
        assert len(tracks1) == 2

    def test_track_history(self):
        """Test that track history records center positions."""
        tracker = MultiObjectTracker()

        det_frame0 = [
            Detection(bbox=(100, 100, 200, 200), class_id=0, confidence=0.9, class_name="person"),
        ]
        tracker.update(det_frame0, frame_num=0)

        det_frame1 = [
            Detection(bbox=(110, 110, 210, 210), class_id=0, confidence=0.9, class_name="person"),
        ]
        tracker.update(det_frame1, frame_num=1)

        track = tracker.get_track(1)
        assert track is not None
        assert len(track.history) == 2
        assert track.history[0] == (150.0, 150.0, 0)
        assert track.history[1] == (160.0, 160.0, 1)

    def test_stale_track_removal(self):
        """Test that tracks are removed after max_age frames without update."""
        tracker = MultiObjectTracker(max_age=2)

        det_frame0 = [
            Detection(bbox=(100, 100, 200, 200), class_id=0, confidence=0.9, class_name="person"),
        ]
        tracker.update(det_frame0, frame_num=0)

        tracker.update([], frame_num=1)
        tracker.update([], frame_num=2)
        tracks = tracker.update([], frame_num=3)

        assert len(tracks) == 0

    def test_reset(self):
        """Test that reset clears all state."""
        tracker = MultiObjectTracker()

        det = [Detection(bbox=(10, 10, 50, 50), class_id=0, confidence=0.9, class_name="person")]
        tracker.update(det, frame_num=0)
        assert tracker.get_track(1) is not None

        tracker.reset()
        assert tracker.get_track(1) is None

    def test_get_track_returns_none_for_invalid_id(self):
        """Test that get_track returns None for non-existent ID."""
        tracker = MultiObjectTracker()
        assert tracker.get_track(999) is None

    def test_track_dataclass(self):
        """Test Track dataclass fields."""
        track = Track(
            id=1,
            bbox=(10.0, 20.0, 30.0, 40.0),
            class_id=0,
            confidence=0.95,
            history=[(20.0, 30.0, 0)],
        )
        assert track.id == 1
        assert track.bbox == (10.0, 20.0, 30.0, 40.0)
        assert track.class_id == 0
        assert track.confidence == 0.95
        assert len(track.history) == 1

    def test_empty_detections_on_first_frame(self):
        """Test behavior when first frame has no detections."""
        tracker = MultiObjectTracker()
        tracks = tracker.update([], frame_num=0)
        assert len(tracks) == 0
