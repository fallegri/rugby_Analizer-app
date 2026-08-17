"""YOLO-based object detection for rugby video analysis.

Uses YOLOv8 via the ultralytics library. Configured for GTX 1060
compatibility (YOLOv8n model for low VRAM usage).
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class Detection:
    """A single object detection result.

    Attributes:
        bbox: Bounding box as (x1, y1, x2, y2) in pixel coordinates.
        class_id: COCO class ID (0=person, 32=sports ball).
        confidence: Detection confidence score [0.0, 1.0].
        class_name: Human-readable class name.
    """

    bbox: tuple[float, float, float, float]
    class_id: int
    confidence: float
    class_name: str


class YOLODetector:
    """YOLO-based object detector for rugby analysis.

    Detects persons (class 0) and sports balls (class 32) in video frames.
    Uses YOLOv8n by default for GTX 1060 compatibility (6GB VRAM).

    Args:
        model_path: Path to YOLO model weights. Defaults to 'yolov8n.pt'.
        confidence_threshold: Minimum confidence for detection. Defaults to 0.25.
        device: Device for inference ('cuda', 'cpu', or 'auto'). Defaults to 'auto'.
        target_classes: List of COCO class IDs to detect. Defaults to [0, 32].
    """

    # COCO class mappings for rugby-relevant objects
    CLASS_NAMES = {
        0: "person",
        32: "sports ball",
    }

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.25,
        device: str = "auto",
        target_classes: Optional[list[int]] = None,
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.target_classes = target_classes or [0, 32]
        self._model = None

    @property
    def model(self):
        """Lazy-load the YOLO model on first use."""
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.model_path)
        return self._model

    def detect_frame(self, frame: np.ndarray) -> list[Detection]:
        """Run detection on a single frame.

        Args:
            frame: Input frame as numpy array (H, W, C) in BGR format.

        Returns:
            List of Detection objects found in the frame.
        """
        results = self.model.predict(
            frame,
            conf=self.confidence_threshold,
            classes=self.target_classes,
            device=self.device if self.device not in ("auto", "") else "cpu",
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detection = Detection(
                    bbox=(x1, y1, x2, y2),
                    class_id=class_id,
                    confidence=confidence,
                    class_name=self.CLASS_NAMES.get(class_id, f"class_{class_id}"),
                )
                detections.append(detection)

        return detections

    def detect_batch(self, frames: list[np.ndarray]) -> list[list[Detection]]:
        """Run detection on a batch of frames.

        Args:
            frames: List of input frames as numpy arrays.

        Returns:
            List of detection lists, one per input frame.
        """
        results = self.model.predict(
            frames,
            conf=self.confidence_threshold,
            classes=self.target_classes,
            device=self.device if self.device != "auto" else None,
            verbose=False,
        )

        batch_detections = []
        for result in results:
            frame_detections = []
            if result.boxes is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = float(box.conf[0].item())
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    detection = Detection(
                        bbox=(x1, y1, x2, y2),
                        class_id=class_id,
                        confidence=confidence,
                        class_name=self.CLASS_NAMES.get(
                            class_id, f"class_{class_id}"
                        ),
                    )
                    frame_detections.append(detection)
            batch_detections.append(frame_detections)

        return batch_detections
