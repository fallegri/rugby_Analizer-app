"""Computer Vision pipeline - YOLO detection, ByteTrack tracking, field calibration."""

from src.cv.detector import YOLODetector, Detection
from src.cv.tracker import MultiObjectTracker, Track
from src.cv.calibration import AutoCalibrator, ManualCalibrator
from src.cv.transform import HomographyTransform
from src.cv.analytics import AnalyticsEngine
from src.cv.tracking_modes import (
    TrackingStrategy,
    SinglePlayerStrategy,
    BallCarrierStrategy,
    BallOnlyStrategy,
    GroupTrackingStrategy,
)
from src.cv.video_processor import VideoProcessor

__all__ = [
    "YOLODetector",
    "Detection",
    "MultiObjectTracker",
    "Track",
    "AutoCalibrator",
    "ManualCalibrator",
    "HomographyTransform",
    "AnalyticsEngine",
    "TrackingStrategy",
    "SinglePlayerStrategy",
    "BallCarrierStrategy",
    "BallOnlyStrategy",
    "GroupTrackingStrategy",
    "VideoProcessor",
]
