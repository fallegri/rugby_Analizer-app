"""Video processing pipeline orchestrating detection, tracking, and analytics.

Processes video files frame-by-frame through the full CV pipeline:
video capture -> detection -> tracking -> coordinate transform -> analytics.
"""

from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable, Optional

import cv2
import numpy as np

from src.cv.analytics import AnalyticsEngine, AnalyticsResult
from src.cv.detector import Detection, YOLODetector
from src.cv.tracker import MultiObjectTracker, Track
from src.cv.tracking_modes import FilteredResult, TrackingStrategy
from src.cv.transform import HomographyTransform


@dataclass
class FrameResult:
    """Result from processing a single frame.

    Attributes:
        frame_num: Frame number in the video.
        detections: Raw detections from the frame.
        tracks: Active tracks after update.
        filtered: Filtered result from tracking strategy.
        field_positions: Transformed field coordinates for filtered tracks.
    """

    frame_num: int
    detections: list[Detection] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    filtered: Optional[FilteredResult] = None
    field_positions: list[tuple[int, float, float]] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis result from processing a video.

    Attributes:
        total_frames: Total number of frames processed.
        fps: Video frames per second.
        duration_s: Video duration in seconds.
        analytics: Per-track analytics results (track_id -> AnalyticsResult).
        frame_results: List of per-frame results (may be empty if not stored).
    """

    total_frames: int = 0
    fps: float = 30.0
    duration_s: float = 0.0
    analytics: dict[int, AnalyticsResult] = field(default_factory=dict)
    frame_results: list[FrameResult] = field(default_factory=list)


class VideoProcessor:
    """Orchestrates the full video analysis pipeline.

    Coordinates detection, tracking, coordinate transformation, and
    analytics computation for rugby video analysis.

    Args:
        detector: YOLODetector instance for object detection.
        tracker: MultiObjectTracker instance for maintaining track IDs.
        transform: HomographyTransform for pixel-to-field mapping (optional).
        tracking_strategy: TrackingStrategy to filter relevant tracks.
        analytics_engine: AnalyticsEngine for computing metrics (optional).
    """

    def __init__(
        self,
        detector: YOLODetector,
        tracker: MultiObjectTracker,
        transform: Optional[HomographyTransform] = None,
        tracking_strategy: Optional[TrackingStrategy] = None,
        analytics_engine: Optional[AnalyticsEngine] = None,
    ):
        self.detector = detector
        self.tracker = tracker
        self.transform = transform
        self.tracking_strategy = tracking_strategy
        self.analytics_engine = analytics_engine
        self._track_histories: dict[int, list[tuple[float, float, int]]] = {}

    def process_video(
        self,
        video_path: str,
        target_ids: Optional[list[int]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        store_frame_results: bool = False,
    ) -> AnalysisResult:
        """Process an entire video file through the pipeline.

        Args:
            video_path: Path to the video file.
            target_ids: Target track IDs for the tracking strategy.
            progress_callback: Called with (current_frame, total_frames).
            store_frame_results: Whether to store per-frame results.

        Returns:
            AnalysisResult with complete analysis data.

        Raises:
            FileNotFoundError: If video file cannot be opened.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.tracker.reset()
        self._track_histories = {}

        result = AnalysisResult(
            total_frames=total_frames,
            fps=fps,
            duration_s=total_frames / fps if fps > 0 else 0.0,
        )

        frame_num = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_result = self._process_single_frame(frame, frame_num, target_ids)

            if store_frame_results:
                result.frame_results.append(frame_result)

            frame_num += 1

            if progress_callback:
                progress_callback(frame_num, total_frames)

        cap.release()
        result.total_frames = frame_num

        if self.analytics_engine:
            for track_id, history in self._track_histories.items():
                if len(history) >= 2:
                    result.analytics[track_id] = self.analytics_engine.compute(history)

        return result

    async def process_video_stream(
        self,
        video_path: str,
        target_ids: Optional[list[int]] = None,
    ) -> AsyncGenerator[FrameResult, None]:
        """Process video as an async generator yielding per-frame results.

        Args:
            video_path: Path to the video file.
            target_ids: Target track IDs for the tracking strategy.

        Yields:
            FrameResult for each processed frame.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        self.tracker.reset()
        self._track_histories = {}

        frame_num = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_result = self._process_single_frame(frame, frame_num, target_ids)
            yield frame_result
            frame_num += 1

        cap.release()

    def process_realtime_stream(
        self,
        stream_url: str,
        target_ids: Optional[list[int]] = None,
        frame_callback: Optional[Callable[[FrameResult], None]] = None,
        max_frames: Optional[int] = None,
    ) -> AnalysisResult:
        """Process a real-time video stream (RTSP/HTTP).

        Args:
            stream_url: URL of the stream (RTSP or HTTP).
            target_ids: Target track IDs for the tracking strategy.
            frame_callback: Called for each processed frame result.
            max_frames: Maximum number of frames to process (None=infinite).

        Returns:
            AnalysisResult with analysis data up to when stream ended.
        """
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            raise ConnectionError(f"Cannot connect to stream: {stream_url}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        self.tracker.reset()
        self._track_histories = {}

        frame_num = 0
        while True:
            if max_frames is not None and frame_num >= max_frames:
                break

            ret, frame = cap.read()
            if not ret:
                break

            frame_result = self._process_single_frame(frame, frame_num, target_ids)

            if frame_callback:
                frame_callback(frame_result)

            frame_num += 1

        cap.release()

        result = AnalysisResult(
            total_frames=frame_num,
            fps=fps,
            duration_s=frame_num / fps if fps > 0 else 0.0,
        )

        if self.analytics_engine:
            for track_id, history in self._track_histories.items():
                if len(history) >= 2:
                    result.analytics[track_id] = self.analytics_engine.compute(history)

        return result

    def _process_single_frame(
        self,
        frame: np.ndarray,
        frame_num: int,
        target_ids: Optional[list[int]],
    ) -> FrameResult:
        """Process a single frame through the pipeline."""
        detections = self.detector.detect_frame(frame)
        tracks = self.tracker.update(detections, frame_num)

        filtered = None
        if self.tracking_strategy:
            filtered = self.tracking_strategy.process_frame(
                frame, detections, tracks, target_ids
            )
            relevant_tracks = filtered.tracks
        else:
            relevant_tracks = tracks

        field_positions = []
        for track in relevant_tracks:
            cx = (track.bbox[0] + track.bbox[2]) / 2.0
            cy = (track.bbox[1] + track.bbox[3]) / 2.0

            if self.transform:
                fx, fy = self.transform.pixel_to_field(cx, cy)
            else:
                fx, fy = cx, cy

            field_positions.append((track.id, fx, fy))

            if track.id not in self._track_histories:
                self._track_histories[track.id] = []
            self._track_histories[track.id].append((fx, fy, frame_num))

        return FrameResult(
            frame_num=frame_num,
            detections=detections,
            tracks=tracks,
            filtered=filtered,
            field_positions=field_positions,
        )
