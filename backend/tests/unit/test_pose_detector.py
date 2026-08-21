"""Unit tests for the PoseDetector module.

All tests mock the ultralytics YOLO model to avoid loading actual weights.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cv.pose_detector import (
    KEYPOINT_NAMES,
    SKELETON_CONNECTIONS,
    PoseDetection,
    PoseDetector,
)


@pytest.fixture
def mock_yolo_pose_model():
    """Create a mock YOLO pose model that returns predictable pose detections."""
    model_instance = MagicMock()
    return model_instance


@pytest.fixture
def pose_detector(mock_yolo_pose_model):
    """Create a PoseDetector with a mocked model."""
    det = PoseDetector(model_path="yolov8s-pose.pt", confidence_threshold=0.25)
    det._model = mock_yolo_pose_model
    return det


class TestPoseDetector:
    """Tests for PoseDetector class."""

    def test_instantiation(self):
        """Test PoseDetector can be instantiated without loading model."""
        det = PoseDetector(
            model_path="yolov8s-pose.pt",
            confidence_threshold=0.5,
            device="cpu",
        )
        assert det.model_path == "yolov8s-pose.pt"
        assert det.confidence_threshold == 0.5
        assert det.device == "cpu"
        assert det._model is None

    def test_default_model_path(self):
        """Test the default pose model is yolov8s-pose.pt."""
        det = PoseDetector()
        assert det.model_path == "yolov8s-pose.pt"

    def test_valid_pose_models(self):
        """Test valid pose model set includes all expected models."""
        expected = {"yolov8n-pose.pt", "yolov8s-pose.pt", "yolov8m-pose.pt", "yolov8l-pose.pt"}
        assert PoseDetector.VALID_POSE_MODELS == expected

    def test_detect_poses_returns_pose_detections(self, pose_detector, mock_yolo_pose_model):
        """Test that detect_poses returns PoseDetection objects with keypoints."""
        # Create mock keypoints data (17 keypoints x 3 values: x, y, conf)
        mock_kp_data = np.array([
            [100.0, 50.0, 0.9],   # nose
            [105.0, 45.0, 0.8],   # left_eye
            [95.0, 45.0, 0.8],    # right_eye
            [110.0, 50.0, 0.7],   # left_ear
            [90.0, 50.0, 0.7],    # right_ear
            [120.0, 80.0, 0.9],   # left_shoulder
            [80.0, 80.0, 0.9],    # right_shoulder
            [130.0, 120.0, 0.8],  # left_elbow
            [70.0, 120.0, 0.8],   # right_elbow
            [135.0, 150.0, 0.7],  # left_wrist
            [65.0, 150.0, 0.7],   # right_wrist
            [115.0, 160.0, 0.9],  # left_hip
            [85.0, 160.0, 0.9],   # right_hip
            [120.0, 220.0, 0.8],  # left_knee
            [80.0, 220.0, 0.8],   # right_knee
            [125.0, 280.0, 0.7],  # left_ankle
            [75.0, 280.0, 0.7],   # right_ankle
        ])

        # Mock box
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [50.0, 30.0, 150.0, 300.0]
        mock_box.cls = [MagicMock()]
        mock_box.cls[0].item.return_value = 0
        mock_box.conf = [MagicMock()]
        mock_box.conf[0].item.return_value = 0.92

        # Mock result with keypoints
        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        mock_result.keypoints = MagicMock()
        mock_result.keypoints.data = np.array([mock_kp_data])

        mock_yolo_pose_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = pose_detector.detect_poses(frame)

        assert len(detections) == 1
        det = detections[0]
        assert isinstance(det, PoseDetection)
        assert det.bbox == (50.0, 30.0, 150.0, 300.0)
        assert det.class_id == 0
        assert det.confidence == 0.92
        assert det.class_name == "person"
        assert len(det.keypoints) == 17
        # Check first keypoint (nose)
        assert det.keypoints[0] == (100.0, 50.0, 0.9)
        # Check last keypoint (right_ankle)
        assert det.keypoints[16] == (75.0, 280.0, 0.7)

    def test_detect_poses_no_detections(self, pose_detector, mock_yolo_pose_model):
        """Test when no poses are detected."""
        mock_result = MagicMock()
        mock_result.boxes = None
        mock_yolo_pose_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = pose_detector.detect_poses(frame)

        assert len(detections) == 0

    def test_detect_poses_no_keypoints_data(self, pose_detector, mock_yolo_pose_model):
        """Test detection when keypoints data is not available."""
        mock_box = MagicMock()
        mock_box.xyxy = [MagicMock()]
        mock_box.xyxy[0].tolist.return_value = [10.0, 20.0, 100.0, 200.0]
        mock_box.cls = [MagicMock()]
        mock_box.cls[0].item.return_value = 0
        mock_box.conf = [MagicMock()]
        mock_box.conf[0].item.return_value = 0.85

        mock_result = MagicMock()
        mock_result.boxes = [mock_box]
        mock_result.keypoints = None

        mock_yolo_pose_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = pose_detector.detect_poses(frame)

        assert len(detections) == 1
        assert detections[0].keypoints == []

    def test_detect_poses_multiple_persons(self, pose_detector, mock_yolo_pose_model):
        """Test detection of multiple persons with keypoints."""
        kp_data_1 = np.random.rand(17, 3) * 100
        kp_data_2 = np.random.rand(17, 3) * 100

        mock_box1 = MagicMock()
        mock_box1.xyxy = [MagicMock()]
        mock_box1.xyxy[0].tolist.return_value = [10.0, 20.0, 100.0, 200.0]
        mock_box1.cls = [MagicMock()]
        mock_box1.cls[0].item.return_value = 0
        mock_box1.conf = [MagicMock()]
        mock_box1.conf[0].item.return_value = 0.90

        mock_box2 = MagicMock()
        mock_box2.xyxy = [MagicMock()]
        mock_box2.xyxy[0].tolist.return_value = [200.0, 50.0, 350.0, 250.0]
        mock_box2.cls = [MagicMock()]
        mock_box2.cls[0].item.return_value = 0
        mock_box2.conf = [MagicMock()]
        mock_box2.conf[0].item.return_value = 0.88

        mock_result = MagicMock()
        mock_result.boxes = [mock_box1, mock_box2]
        mock_result.keypoints = MagicMock()
        mock_result.keypoints.data = np.array([kp_data_1, kp_data_2])

        mock_yolo_pose_model.predict.return_value = [mock_result]

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = pose_detector.detect_poses(frame)

        assert len(detections) == 2
        assert all(isinstance(d, PoseDetection) for d in detections)
        assert len(detections[0].keypoints) == 17
        assert len(detections[1].keypoints) == 17

    def test_lazy_model_loading(self):
        """Test that model is not loaded until first use."""
        det = PoseDetector(model_path="yolov8s-pose.pt")
        assert det._model is None

    def test_pose_detection_inherits_detection(self):
        """Test that PoseDetection extends Detection properly."""
        pose_det = PoseDetection(
            bbox=(10.0, 20.0, 100.0, 200.0),
            class_id=0,
            confidence=0.9,
            class_name="person",
            keypoints=[(50.0, 30.0, 0.95)],
        )
        assert pose_det.bbox == (10.0, 20.0, 100.0, 200.0)
        assert pose_det.class_id == 0
        assert pose_det.confidence == 0.9
        assert pose_det.class_name == "person"
        assert len(pose_det.keypoints) == 1
        assert pose_det.keypoints[0] == (50.0, 30.0, 0.95)


class TestKeypoints:
    """Tests for keypoint constants and skeleton connections."""

    def test_coco_keypoint_count(self):
        """Test that we have 17 COCO keypoint names defined."""
        assert len(KEYPOINT_NAMES) == 17

    def test_keypoint_names_order(self):
        """Test that keypoint names follow COCO format ordering."""
        assert KEYPOINT_NAMES[0] == "nose"
        assert KEYPOINT_NAMES[5] == "left_shoulder"
        assert KEYPOINT_NAMES[6] == "right_shoulder"
        assert KEYPOINT_NAMES[11] == "left_hip"
        assert KEYPOINT_NAMES[12] == "right_hip"
        assert KEYPOINT_NAMES[16] == "right_ankle"

    def test_skeleton_connections_valid(self):
        """Test that all skeleton connections reference valid keypoint indices."""
        for i, j in SKELETON_CONNECTIONS:
            assert 0 <= i < 17, f"Invalid keypoint index {i}"
            assert 0 <= j < 17, f"Invalid keypoint index {j}"

    def test_skeleton_connections_count(self):
        """Test skeleton connections include the expected body segments."""
        # Should have at least shoulders, torso, and legs
        assert len(SKELETON_CONNECTIONS) >= 10
