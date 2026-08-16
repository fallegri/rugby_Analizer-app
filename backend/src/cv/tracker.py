"""Multi-object tracker using IoU-based assignment (ByteTrack-style).

Maintains consistent track IDs across frames for rugby player and ball tracking.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.cv.detector import Detection


@dataclass
class Track:
    """A tracked object across multiple frames.

    Attributes:
        id: Unique track identifier.
        bbox: Current bounding box as (x1, y1, x2, y2).
        class_id: COCO class ID of the tracked object.
        confidence: Latest detection confidence.
        history: List of (center_x, center_y, frame_num) tuples.
    """

    id: int
    bbox: tuple[float, float, float, float]
    class_id: int
    confidence: float
    history: list[tuple[float, float, int]] = field(default_factory=list)


def _iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    """Compute Intersection over Union between two bounding boxes.

    Args:
        box_a: Bounding box as (x1, y1, x2, y2).
        box_b: Bounding box as (x1, y1, x2, y2).

    Returns:
        IoU value in [0.0, 1.0].
    """
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if inter_area == 0.0:
        return 0.0

    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union_area = area_a + area_b - inter_area

    if union_area == 0.0:
        return 0.0

    return inter_area / union_area


class MultiObjectTracker:
    """IoU-based multi-object tracker (ByteTrack-style).

    Assigns detections to existing tracks using IoU similarity.
    Creates new tracks for unmatched detections and removes
    stale tracks that have not been updated recently.

    Args:
        iou_threshold: Minimum IoU to match a detection to a track.
        max_age: Number of frames a track can survive without update.
        min_hits: Minimum number of hits before a track is confirmed.
    """

    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_age: int = 30,
        min_hits: int = 3,
    ):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self._tracks: list[Track] = []
        self._next_id: int = 1
        self._ages: dict[int, int] = {}
        self._hit_counts: dict[int, int] = {}

    def update(self, detections: list[Detection], frame_num: int) -> list[Track]:
        """Update tracks with new detections from a frame.

        Performs IoU-based matching between existing tracks and new detections.
        Creates new tracks for unmatched detections and removes stale tracks.

        Args:
            detections: List of detections from the current frame.
            frame_num: Current frame number for history tracking.

        Returns:
            List of active tracks after the update.
        """
        if not self._tracks:
            for det in detections:
                self._create_track(det, frame_num)
            return list(self._tracks)

        if not detections:
            self._age_tracks()
            return list(self._tracks)

        num_tracks = len(self._tracks)
        num_dets = len(detections)
        iou_matrix = np.zeros((num_tracks, num_dets))

        for i, track in enumerate(self._tracks):
            for j, det in enumerate(detections):
                iou_matrix[i, j] = _iou(track.bbox, det.bbox)

        matched_tracks = set()
        matched_dets = set()

        while True:
            if iou_matrix.size == 0:
                break
            max_iou = iou_matrix.max()
            if max_iou < self.iou_threshold:
                break

            idx = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
            track_idx, det_idx = int(idx[0]), int(idx[1])

            track = self._tracks[track_idx]
            det = detections[det_idx]
            track.bbox = det.bbox
            track.confidence = det.confidence
            track.class_id = det.class_id

            cx = (det.bbox[0] + det.bbox[2]) / 2.0
            cy = (det.bbox[1] + det.bbox[3]) / 2.0
            track.history.append((cx, cy, frame_num))

            self._ages[track.id] = 0
            self._hit_counts[track.id] = self._hit_counts.get(track.id, 0) + 1

            matched_tracks.add(track_idx)
            matched_dets.add(det_idx)

            iou_matrix[track_idx, :] = 0.0
            iou_matrix[:, det_idx] = 0.0

        for j, det in enumerate(detections):
            if j not in matched_dets:
                self._create_track(det, frame_num)

        for i in range(num_tracks):
            if i not in matched_tracks:
                track = self._tracks[i]
                self._ages[track.id] = self._ages.get(track.id, 0) + 1

        self._tracks = [
            t for t in self._tracks
            if self._ages.get(t.id, 0) <= self.max_age
        ]

        return list(self._tracks)

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get a specific track by ID.

        Args:
            track_id: The unique track identifier.

        Returns:
            The Track object if found, None otherwise.
        """
        for track in self._tracks:
            if track.id == track_id:
                return track
        return None

    def reset(self) -> None:
        """Reset the tracker, clearing all tracks and state."""
        self._tracks = []
        self._next_id = 1
        self._ages = {}
        self._hit_counts = {}

    def _create_track(self, detection: Detection, frame_num: int) -> Track:
        """Create a new track from a detection."""
        cx = (detection.bbox[0] + detection.bbox[2]) / 2.0
        cy = (detection.bbox[1] + detection.bbox[3]) / 2.0

        track = Track(
            id=self._next_id,
            bbox=detection.bbox,
            class_id=detection.class_id,
            confidence=detection.confidence,
            history=[(cx, cy, frame_num)],
        )

        self._tracks.append(track)
        self._ages[track.id] = 0
        self._hit_counts[track.id] = 1
        self._next_id += 1

        return track

    def _age_tracks(self) -> None:
        """Increment age of all tracks and remove stale ones."""
        for track in self._tracks:
            self._ages[track.id] = self._ages.get(track.id, 0) + 1

        self._tracks = [
            t for t in self._tracks
            if self._ages.get(t.id, 0) <= self.max_age
        ]
