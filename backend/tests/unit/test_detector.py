"""Unit tests for the YOLO detector module.

All tests mock the ultralytics YOLO model to avoid loading actual weights.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cv.detector import Detection, YOLODetector


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model that returns predictable detections."""
    model_instance = MagicMock()
    return model_instance


@pytest.fixture
def detector(mock_yolo_model):
    """Create a YOLODetector with a mocked model."""
    det = YOLODetector(model_path="yolov8n.pt", confidence_threshold=0.25)
    det._model = mock_yolo_model
    return det


class TestYOLODetector:
    """Tests for YOLODetector class."""

    def test_instantiation(self):
        """Test detector can be instantiated without loading model."""
        det = YOLODetector(
            model_path="yolov8n.pt",
            confidence_threshold=0.5,
            device="cpu",
        )
        assert det.model_path == "yolov8n.pt"
        assert det.confidence_threshold == 0.5
        assert det.device == "cpu"
        assert det.target_classes == [0, 32]
        assert det._model is None

    def test_detect_frame_person(self, detector, mock_yolo_model):
        """Test detection of a person (class 0)."""
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [100.0, 200.0, 300.0, 400.0]
        mock_box.cls = [MagicMock()]
        mock_box.cls[0].item.return_value = 0
        mock_box.conf = [MagicMock()]
        mock_box.conf[0].item.return_value = 0.95

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        mock_yolo_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect_frame(frame)

        assert len(detections) == 1
        assert isinstance(detections[0], Detection)
        assert detections[0].bbox == (100.0, 200.0, 300.0, 400.0)
        assert detections[0].class_id == 0
        assert detections[0].confidence == 0.95
        assert detections[0].class_name == "person"

    def test_detect_frame_ball(self, detector, mock_yolo_model):
        """Test detection of a sports ball (class 32)."""
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [50.0, 60.0, 80.0, 90.0]
        mock_box.cls = [MagicMock()]
        mock_box.cls[0].item.return_value = 32
        mock_box.conf = [MagicMock()]
        mock_box.conf[0].item.return_value = 0.88

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        mock_yolo_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect_frame(frame)

        assert len(detections) == 1
        assert detections[0].class_id == 32
        assert detections[0].class_name == "sports ball"
        assert detections[0].confidence == 0.88

    def test_detect_frame_multiple_detections(self, detector, mock_yolo_model):
        """Test multiple detections in a single frame."""
        mock_box1 = MagicMock()
        mock_box1.xyxy = [MagicMock()]
        mock_box1.xyxy[0].tolist.return_value = [10.0, 20.0, 50.0, 60.0]
        mock_box1.cls = [MagicMock()]
        mock_box1.cls[0].item.return_value = 0
        mock_box1.conf = [MagicMock()]
        mock_box1.conf[0].item.return_value = 0.90

        mock_box2 = MagicMock()
        mock_box2.xyxy = [MagicMock()]
        mock_box2.xyxy[0].tolist.return_value = [200.0, 100.0, 250.0, 150.0]
        mock_box2.cls = [MagicMock()]
        mock_box2.cls[0].item.return_value = 32
        mock_box2.conf = [MagicMock()]
        mock_box2.conf[0].item.return_value = 0.75

        mock_result = MagicMock()
        mock_result.boxes = [mock_box1, mock_box2]
        mock_yolo_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect_frame(frame)

        assert len(detections) == 2
        assert detections[0].class_id == 0
        assert detections[1].class_id == 32

    def test_detect_frame_no_detections(self, detector, mock_yolo_model):
        """Test when no objects are detected."""
        mock_result = MagicMock()
        mock_result.boxes = None
        mock_yolo_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect_frame(frame)

        assert len(detections) == 0

    def test_detect_batch(self, detector, mock_yolo_model):
        """Test batch detection on multiple frames."""
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [10.0, 20.0, 50.0, 60.0]
        mock_box.cls = [MagicMock()]
        mock_box.cls[0].item.return_value = 0
        mock_box.conf = [MagicMock()]
        mock_box.conf[0].item.return_value = 0.85

        mock_result1 = MagicMock()
        mock_result1.boxes = [mock_box]
        mock_result2 = MagicMock()
        mock_result2.boxes = None

        mock_yolo_model.predict.return_value = [mock_result1, mock_result2]

        frames = [
            np.zeros((480, 640, 3), dtype=np.uint8),
            np.zeros((480, 640, 3), dtype=np.uint8),
        ]
        batch_results = detector.detect_batch(frames)

        assert len(batch_results) == 2
        assert len(batch_results[0]) == 1
        assert len(batch_results[1]) == 0

    def test_detection_dataclass(self):
        """Test Detection dataclass fields."""
        det = Detection(
            bbox=(10.0, 20.0, 30.0, 40.0),
            class_id=0,
            confidence=0.92,
            class_name="person",
        )
        assert det.bbox == (10.0, 20.0, 30.0, 40.0)
        assert det.class_id == 0
        assert det.confidence == 0.92
        assert det.class_name == "person"

    def test_default_target_classes(self):
        """Test default target classes include person and ball."""
        det = YOLODetector()
        assert 0 in det.target_classes
        assert 32 in det.target_classes

    def test_custom_target_classes(self):
        """Test custom target class configuration."""
        det = YOLODetector(target_classes=[0])
        assert det.target_classes == [0]
