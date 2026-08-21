"""YOLOv8-pose based posture/skeleton detection for rugby analysis.

Uses YOLOv8-pose to extract keypoints (skeleton) from detected players.
Enables posture analysis for better tackle detection and play classification.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.cv.detector import Detection


# COCO keypoint indices for reference
KEYPOINT_NAMES = [
    "nose",           # 0
    "left_eye",       # 1
    "right_eye",      # 2
    "left_ear",       # 3
    "right_ear",      # 4
    "left_shoulder",  # 5
    "right_shoulder", # 6
    "left_elbow",     # 7
    "right_elbow",    # 8
    "left_wrist",     # 9
    "right_wrist",    # 10
    "left_hip",       # 11
    "right_hip",      # 12
    "left_knee",      # 13
    "right_knee",     # 14
    "left_ankle",     # 15
    "right_ankle",    # 16
]

# Skeleton connections for rendering (pairs of keypoint indices)
SKELETON_CONNECTIONS = [
    (5, 6),    # shoulders
    (5, 7),    # left shoulder - left elbow
    (7, 9),    # left elbow - left wrist
    (6, 8),    # right shoulder - right elbow
    (8, 10),   # right elbow - right wrist
    (5, 11),   # left shoulder - left hip
    (6, 12),   # right shoulder - right hip
    (11, 12),  # hips
    (11, 13),  # left hip - left knee
    (13, 15),  # left knee - left ankle
    (12, 14),  # right hip - right knee
    (14, 16),  # right knee - right ankle
]


@dataclass
class PoseDetection(Detection):
    """A detection with keypoints (skeleton) information.

    Extends Detection with COCO format keypoints (17 points).
    Each keypoint is a tuple of (x, y, confidence).

    Attributes:
        keypoints: List of 17 (x, y, confidence) tuples for COCO keypoints.
    """

    keypoints: list[tuple[float, float, float]] = field(default_factory=list)


class PoseDetector:
    """YOLOv8-pose based skeleton/posture detector.

    Detects human poses with 17 COCO keypoints for posture analysis.
    Used alongside the main object detector to provide skeleton data
    for enhanced play detection (tackles, scrums, etc.).

    Args:
        model_path: Path to YOLOv8-pose model weights. Defaults to 'yolov8s-pose.pt'.
        confidence_threshold: Minimum confidence for detection. Defaults to 0.25.
        device: Device for inference ('cuda', 'cpu', or 'auto'). Defaults to 'auto'.
    """

    VALID_POSE_MODELS = {"yolov8n-pose.pt", "yolov8s-pose.pt", "yolov8m-pose.pt", "yolov8l-pose.pt"}

    def __init__(
        self,
        model_path: str = "yolov8s-pose.pt",
        confidence_threshold: float = 0.25,
        device: str = "auto",
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self._model = None

    @property
    def model(self):
        """Lazy-load the YOLO pose model on first use."""
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.model_path)
        return self._model

    def detect_poses(self, frame: np.ndarray) -> list[PoseDetection]:
        """Run pose detection on a single frame.

        Args:
            frame: Input frame as numpy array (H, W, C) in BGR format.

        Returns:
            List of PoseDetection objects with keypoints for each person detected.
        """
        results = self.model.predict(
            frame,
            conf=self.confidence_threshold,
            device=self.device if self.device not in ("auto", "") else "cpu",
            verbose=False,
        )

        pose_detections = []
        for result in results:
            if result.boxes is None:
                continue

            # Get keypoints data if available
            keypoints_data = None
            if hasattr(result, "keypoints") and result.keypoints is not None:
                keypoints_data = result.keypoints.data

            for i, box in enumerate(result.boxes):
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                # Extract keypoints for this detection
                kps: list[tuple[float, float, float]] = []
                if keypoints_data is not None and i < len(keypoints_data):
                    kp_array = keypoints_data[i]  # Shape: (17, 3) - x, y, conf
                    for kp_idx in range(min(17, len(kp_array))):
                        kp_x = float(kp_array[kp_idx][0])
                        kp_y = float(kp_array[kp_idx][1])
                        kp_conf = float(kp_array[kp_idx][2]) if kp_array.shape[1] > 2 else 0.0
                        kps.append((kp_x, kp_y, kp_conf))

                pose_detections.append(PoseDetection(
                    bbox=(x1, y1, x2, y2),
                    class_id=class_id,
                    confidence=confidence,
                    class_name="person",
                    keypoints=kps,
                ))

        return pose_detections
