"""Video processing pipeline orchestrating detection, tracking, and analytics.

Processes video files frame-by-frame through the full CV pipeline:
video capture -> detection -> tracking -> coordinate transform -> analytics.
"""

from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable, Optional, Union

import cv2
import numpy as np

from src.cv.analytics import AnalyticsEngine, AnalyticsResult
from src.cv.detector import Detection, YOLODetector
from src.cv.tracker import MultiObjectTracker, Track
from src.cv.tracking_modes import FilteredResult, TrackingStrategy
from src.cv.transform import DefaultFieldTransform, HomographyTransform, LinearFieldTransform

# Type alias for any supported transform
AnyTransform = Union[HomographyTransform, LinearFieldTransform, DefaultFieldTransform]


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

    When no transform is provided, a DefaultFieldTransform is used that
    assumes the visible frame covers approximately 60m x 40m of the field.
    This prevents raw pixel values (0-1920) from being treated as meters.

    Args:
        detector: YOLODetector instance for object detection.
        tracker: MultiObjectTracker instance for maintaining track IDs.
        transform: Any field transform for pixel-to-field mapping (optional).
        tracking_strategy: TrackingStrategy to filter relevant tracks.
        analytics_engine: AnalyticsEngine for computing metrics (optional).
        frame_width: Expected frame width in pixels (used for default transform).
        frame_height: Expected frame height in pixels (used for default transform).
        player_selection_boxes: List of bounding boxes from user player selections.
            Each is a dict with keys x, y, width, height in pixel coordinates.
            Used for target acquisition in single/group player modes.
    """

    def __init__(
        self,
        detector: YOLODetector,
        tracker: MultiObjectTracker,
        transform: Optional[AnyTransform] = None,
        tracking_strategy: Optional[TrackingStrategy] = None,
        analytics_engine: Optional[AnalyticsEngine] = None,
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
        player_selection_boxes: Optional[list[dict]] = None,
    ):
        self.detector = detector
        self.tracker = tracker
        self.transform = transform
        self.tracking_strategy = tracking_strategy
        self.analytics_engine = analytics_engine
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.player_selection_boxes = player_selection_boxes or []
        self._track_histories: dict[int, list[tuple[float, float, int]]] = {}
        # Target acquisition: maps selection index -> acquired track ID
        self._acquired_targets: dict[int, int] = {}
        # Number of frames to search for target acquisition
        self._acquisition_frames = 10

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

        # Update frame dimensions from actual video
        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_width > 0:
            self.frame_width = actual_width
        if actual_height > 0:
            self.frame_height = actual_height

        # If no transform is set, create a default one using actual frame dimensions
        if self.transform is None:
            self.transform = DefaultFieldTransform(
                frame_width=self.frame_width,
                frame_height=self.frame_height,
            )

        self.tracker.reset()
        self._track_histories = {}
        self._acquired_targets = {}

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

            # During the acquisition phase, try to match user selections to tracks
            effective_target_ids = self._get_effective_target_ids(target_ids, frame_num)

            frame_result = self._process_single_frame(frame, frame_num, effective_target_ids)

            # Target acquisition: match tracks to user selections in early frames
            if frame_num < self._acquisition_frames and self.player_selection_boxes:
                self._try_acquire_targets(frame_result.tracks)

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

        # Update frame dimensions and set default transform if needed
        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_width > 0:
            self.frame_width = actual_width
        if actual_height > 0:
            self.frame_height = actual_height

        if self.transform is None:
            self.transform = DefaultFieldTransform(
                frame_width=self.frame_width,
                frame_height=self.frame_height,
            )

        self.tracker.reset()
        self._track_histories = {}
        self._acquired_targets = {}

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

        # Update frame dimensions and set default transform if needed
        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_width > 0:
            self.frame_width = actual_width
        if actual_height > 0:
            self.frame_height = actual_height

        if self.transform is None:
            self.transform = DefaultFieldTransform(
                frame_width=self.frame_width,
                frame_height=self.frame_height,
            )

        self.tracker.reset()
        self._track_histories = {}
        self._acquired_targets = {}

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

            # Always use transform (DefaultFieldTransform is set if no calibration)
            if self.transform:
                fx, fy = self.transform.pixel_to_field(cx, cy)
            else:
                # Fallback: scale to approximate field coordinates
                fx = (cx / self.frame_width) * 60.0 + 20.0
                fy = (cy / self.frame_height) * 40.0 + 15.0

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

    def _compute_iou(self, box_a: tuple, box_b: dict) -> float:
        """Compute Intersection over Union between a track bbox and a selection box.

        Args:
            box_a: Track bounding box as (x1, y1, x2, y2).
            box_b: User selection box as dict with x, y, width, height.

        Returns:
            IoU value between 0 and 1.
        """
        # box_a: (x1, y1, x2, y2)
        ax1, ay1, ax2, ay2 = box_a

        # box_b: {x, y, width, height} in pixel coords
        bx1 = box_b.get("x", 0)
        by1 = box_b.get("y", 0)
        bx2 = bx1 + box_b.get("width", 0)
        by2 = by1 + box_b.get("height", 0)

        # Intersection
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        if ix2 <= ix1 or iy2 <= iy1:
            return 0.0

        intersection = (ix2 - ix1) * (iy2 - iy1)
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - intersection

        if union <= 0:
            return 0.0

        return intersection / union

    def _try_acquire_targets(self, tracks: list[Track]) -> None:
        """Try to match user selection boxes to detected tracks via IoU.

        In the first few frames, find which track best overlaps with each
        user-drawn bounding box. Once a match is found with sufficient IoU,
        that track ID is "acquired" as the target.

        Args:
            tracks: Current active tracks from the tracker.
        """
        for sel_idx, sel_box in enumerate(self.player_selection_boxes):
            if sel_idx in self._acquired_targets:
                continue  # Already acquired

            best_iou = 0.0
            best_track_id = None

            for track in tracks:
                iou = self._compute_iou(track.bbox, sel_box)
                if iou > best_iou:
                    best_iou = iou
                    best_track_id = track.id

            # Require minimum IoU of 0.2 to accept the match
            if best_track_id is not None and best_iou >= 0.2:
                self._acquired_targets[sel_idx] = best_track_id

    def _get_effective_target_ids(
        self, original_target_ids: Optional[list[int]], frame_num: int
    ) -> Optional[list[int]]:
        """Get the effective target IDs, using acquired targets when available.

        If player_selection_boxes are provided, use the acquired track IDs
        instead of the original target_ids (which may be timestamp-based
        and not match YOLO track IDs).

        Args:
            original_target_ids: The original target IDs from the request.
            frame_num: Current frame number.

        Returns:
            List of effective integer track IDs, or None.
        """
        if self.player_selection_boxes:
            # Use acquired targets
            acquired_ids = list(self._acquired_targets.values())
            if acquired_ids:
                return acquired_ids
            # During acquisition phase, track all (no filtering)
            if frame_num < self._acquisition_frames:
                return None
            # After acquisition with no matches, fall back to original
            return original_target_ids
        return original_target_ids
