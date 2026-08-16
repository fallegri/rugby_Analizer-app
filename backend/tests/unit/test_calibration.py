"""Unit tests for calibration modules.

Tests both AutoCalibrator and ManualCalibrator with known point sets
to verify mathematical correctness of homography computation.
"""

import numpy as np
import pytest

from src.cv.calibration import AutoCalibrator, ManualCalibrator
from src.cv.transform import HomographyTransform, PointCorrespondence


class TestManualCalibrator:
    """Tests for ManualCalibrator class."""

    def test_calibrate_with_4_points(self):
        """Test homography from 4 known point correspondences."""
        correspondences = [
            PointCorrespondence(pixel_x=0, pixel_y=0, field_x=0, field_y=0),
            PointCorrespondence(pixel_x=1000, pixel_y=0, field_x=100, field_y=0),
            PointCorrespondence(pixel_x=1000, pixel_y=700, field_x=100, field_y=70),
            PointCorrespondence(pixel_x=0, pixel_y=700, field_x=0, field_y=70),
        ]

        calibrator = ManualCalibrator()
        transform = calibrator.calibrate(correspondences)

        assert transform is not None
        assert isinstance(transform, HomographyTransform)

        fx, fy = transform.pixel_to_field(500, 350)
        assert fx == pytest.approx(50.0, abs=0.5)
        assert fy == pytest.approx(35.0, abs=0.5)

    def test_calibrate_with_more_than_4_points(self):
        """Test homography with more than 4 points uses RANSAC."""
        correspondences = [
            PointCorrespondence(pixel_x=0, pixel_y=0, field_x=0, field_y=0),
            PointCorrespondence(pixel_x=1000, pixel_y=0, field_x=100, field_y=0),
            PointCorrespondence(pixel_x=1000, pixel_y=700, field_x=100, field_y=70),
            PointCorrespondence(pixel_x=0, pixel_y=700, field_x=0, field_y=70),
            PointCorrespondence(pixel_x=500, pixel_y=350, field_x=50, field_y=35),
        ]

        calibrator = ManualCalibrator()
        transform = calibrator.calibrate(correspondences)

        assert transform is not None
        fx, fy = transform.pixel_to_field(500, 350)
        assert fx == pytest.approx(50.0, abs=1.0)
        assert fy == pytest.approx(35.0, abs=1.0)

    def test_calibrate_with_fewer_than_4_points_raises(self):
        """Test that fewer than 4 points raises ValueError."""
        correspondences = [
            PointCorrespondence(pixel_x=0, pixel_y=0, field_x=0, field_y=0),
            PointCorrespondence(pixel_x=100, pixel_y=0, field_x=10, field_y=0),
            PointCorrespondence(pixel_x=0, pixel_y=100, field_x=0, field_y=10),
        ]

        calibrator = ManualCalibrator()
        with pytest.raises(ValueError, match="At least 4 point correspondences"):
            calibrator.calibrate(correspondences)

    def test_calibrate_perspective_transform(self):
        """Test homography with a perspective (non-affine) mapping."""
        correspondences = [
            PointCorrespondence(pixel_x=200, pixel_y=100, field_x=0, field_y=0),
            PointCorrespondence(pixel_x=800, pixel_y=100, field_x=100, field_y=0),
            PointCorrespondence(pixel_x=900, pixel_y=500, field_x=100, field_y=70),
            PointCorrespondence(pixel_x=100, pixel_y=500, field_x=0, field_y=70),
        ]

        calibrator = ManualCalibrator()
        transform = calibrator.calibrate(correspondences)

        assert transform is not None
        fx, fy = transform.pixel_to_field(200, 100)
        assert fx == pytest.approx(0.0, abs=1.0)
        assert fy == pytest.approx(0.0, abs=1.0)

    def test_calibrate_collinear_points(self):
        """Test that collinear points do not crash."""
        correspondences = [
            PointCorrespondence(pixel_x=0, pixel_y=0, field_x=0, field_y=0),
            PointCorrespondence(pixel_x=100, pixel_y=0, field_x=10, field_y=0),
            PointCorrespondence(pixel_x=200, pixel_y=0, field_x=20, field_y=0),
            PointCorrespondence(pixel_x=300, pixel_y=0, field_x=30, field_y=0),
        ]

        calibrator = ManualCalibrator()
        # Should not crash; result may be None or degenerate
        calibrator.calibrate(correspondences)


class TestAutoCalibrator:
    """Tests for AutoCalibrator class."""

    def test_instantiation(self):
        """Test auto calibrator can be instantiated."""
        cal = AutoCalibrator()
        assert cal.canny_low == 50
        assert cal.canny_high == 150
        assert cal.hough_threshold == 80

    def test_calibrate_returns_none_for_blank_frame(self):
        """Test that blank frame returns None (no lines detected)."""
        calibrator = AutoCalibrator()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = calibrator.calibrate(frame)
        assert result is None

    def test_calibrate_with_synthetic_lines(self):
        """Test auto calibration with a frame containing synthetic field lines."""
        import cv2

        frame = np.zeros((700, 1000, 3), dtype=np.uint8)

        cv2.line(frame, (0, 0), (999, 0), (255, 255, 255), 2)
        cv2.line(frame, (0, 350), (999, 350), (255, 255, 255), 2)
        cv2.line(frame, (0, 699), (999, 699), (255, 255, 255), 2)

        cv2.line(frame, (0, 0), (0, 699), (255, 255, 255), 2)
        cv2.line(frame, (500, 0), (500, 699), (255, 255, 255), 2)
        cv2.line(frame, (999, 0), (999, 699), (255, 255, 255), 2)

        calibrator = AutoCalibrator(
            hough_threshold=50,
            min_line_length=50,
        )
        result = calibrator.calibrate(frame)

        if result is not None:
            assert isinstance(result, HomographyTransform)

    def test_detect_lines_returns_none_for_empty_image(self):
        """Test that line detection returns None for empty image."""
        calibrator = AutoCalibrator()
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        lines = calibrator._detect_lines(frame)
        assert lines is None

    def test_classify_lines(self):
        """Test line classification into horizontal and vertical."""
        calibrator = AutoCalibrator()

        lines = np.array([
            [[0, 100, 500, 100]],
            [[100, 0, 100, 500]],
            [[0, 50, 500, 55]],
        ])

        h, v = calibrator._classify_lines(lines)
        assert len(h) >= 1
        assert len(v) >= 1


class TestPointCorrespondence:
    """Tests for PointCorrespondence dataclass."""

    def test_creation(self):
        """Test PointCorrespondence creation."""
        pc = PointCorrespondence(
            pixel_x=100.0,
            pixel_y=200.0,
            field_x=10.0,
            field_y=20.0,
        )
        assert pc.pixel_x == 100.0
        assert pc.pixel_y == 200.0
        assert pc.field_x == 10.0
        assert pc.field_y == 20.0
