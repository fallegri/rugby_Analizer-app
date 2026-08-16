"""Tracking mode strategies for different rugby analysis scenarios.

Implements the Strategy pattern to support multiple tracking modes:
- Single player tracking
- Ball carrier tracking (auto-switch to player nearest ball)
- Ball only tracking
- Group tracking (multiple selected players)
"""

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from src.cv.detector import Detection
from src.cv.tracker import Track


@dataclass
class FilteredResult:
    """Result from applying a tracking strategy.

    Attributes:
        tracks: List of tracks that passed the strategy filter.
        primary_track_id: The main track of interest (if applicable).
        ball_track_id: The ball track ID (if detected).
    """

    tracks: list[Track] = field(default_factory=list)
    primary_track_id: Optional[int] = None
    ball_track_id: Optional[int] = None


class TrackingStrategy(ABC):
    """Base class for tracking mode strategies.

    Each strategy defines how to filter detections and tracks
    based on the specific analysis mode.
    """

    @abstractmethod
    def process_frame(
        self,
        frame,
        detections: list[Detection],
        tracks: list[Track],
        target_ids: Optional[list[int]] = None,
    ) -> FilteredResult:
        """Process a frame and filter tracks based on strategy.

        Args:
            frame: Current video frame (numpy array).
            detections: Raw detections from the current frame.
            tracks: Active tracks after tracker update.
            target_ids: Optional list of target track IDs.

        Returns:
            FilteredResult with relevant tracks for this mode.
        """
        ...


class SinglePlayerStrategy(TrackingStrategy):
    """Track a single selected player.

    Filters to keep only the track matching the target player ID.
    """

    def process_frame(
        self,
        frame,
        detections: list[Detection],
        tracks: list[Track],
        target_ids: Optional[list[int]] = None,
    ) -> FilteredResult:
        """Filter tracks to the single target player."""
        if not target_ids or len(target_ids) == 0:
            return FilteredResult(tracks=[], primary_track_id=None)

        target_id = target_ids[0]
        filtered = [t for t in tracks if t.id == target_id]

        return FilteredResult(
            tracks=filtered,
            primary_track_id=target_id if filtered else None,
        )


class BallCarrierStrategy(TrackingStrategy):
    """Track the player currently carrying the ball.

    Finds the ball track, then identifies the nearest person track
    to the ball position.
    """

    PERSON_CLASS = 0
    BALL_CLASS = 32

    def process_frame(
        self,
        frame,
        detections: list[Detection],
        tracks: list[Track],
        target_ids: Optional[list[int]] = None,
    ) -> FilteredResult:
        """Find the player nearest to the ball."""
        ball_tracks = [t for t in tracks if t.class_id == self.BALL_CLASS]
        person_tracks = [t for t in tracks if t.class_id == self.PERSON_CLASS]

        if not ball_tracks or not person_tracks:
            return FilteredResult(tracks=person_tracks[:1], primary_track_id=None)

        ball_track = max(ball_tracks, key=lambda t: t.confidence)
        ball_center = (
            (ball_track.bbox[0] + ball_track.bbox[2]) / 2.0,
            (ball_track.bbox[1] + ball_track.bbox[3]) / 2.0,
        )

        nearest_track = None
        min_dist = float("inf")

        for track in person_tracks:
            center = (
                (track.bbox[0] + track.bbox[2]) / 2.0,
                (track.bbox[1] + track.bbox[3]) / 2.0,
            )
            dist = math.sqrt(
                (center[0] - ball_center[0]) ** 2
                + (center[1] - ball_center[1]) ** 2
            )
            if dist < min_dist:
                min_dist = dist
                nearest_track = track

        result_tracks = []
        if nearest_track:
            result_tracks.append(nearest_track)

        return FilteredResult(
            tracks=result_tracks,
            primary_track_id=nearest_track.id if nearest_track else None,
            ball_track_id=ball_track.id,
        )


class BallOnlyStrategy(TrackingStrategy):
    """Track only the rugby ball.

    Filters to keep only ball (sports ball class 32) detections/tracks.
    """

    BALL_CLASS = 32

    def process_frame(
        self,
        frame,
        detections: list[Detection],
        tracks: list[Track],
        target_ids: Optional[list[int]] = None,
    ) -> FilteredResult:
        """Filter tracks to ball only."""
        ball_tracks = [t for t in tracks if t.class_id == self.BALL_CLASS]

        primary_id = None
        if ball_tracks:
            primary = max(ball_tracks, key=lambda t: t.confidence)
            primary_id = primary.id

        return FilteredResult(
            tracks=ball_tracks,
            primary_track_id=primary_id,
            ball_track_id=primary_id,
        )


class GroupTrackingStrategy(TrackingStrategy):
    """Track a group of selected players simultaneously.

    Filters to keep tracks matching multiple specified track IDs.
    """

    def process_frame(
        self,
        frame,
        detections: list[Detection],
        tracks: list[Track],
        target_ids: Optional[list[int]] = None,
    ) -> FilteredResult:
        """Filter tracks to the specified group."""
        if not target_ids:
            return FilteredResult(tracks=[], primary_track_id=None)

        target_set = set(target_ids)
        filtered = [t for t in tracks if t.id in target_set]

        primary_id = filtered[0].id if filtered else None

        return FilteredResult(
            tracks=filtered,
            primary_track_id=primary_id,
        )
