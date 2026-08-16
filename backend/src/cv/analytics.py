"""Analytics engine for computing player/ball metrics from track histories.

Computes distance, speed, sprint segments, and route data from
field-coordinate trajectories and video frame rate information.
"""

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SprintSegment:
    """A segment where the tracked object was sprinting.

    Attributes:
        start_frame: Frame number where the sprint started.
        end_frame: Frame number where the sprint ended.
        start_position: (field_x, field_y) at sprint start.
        end_position: (field_x, field_y) at sprint end.
        max_speed_kmh: Maximum speed during this segment.
        distance_m: Distance covered during this segment.
    """

    start_frame: int
    end_frame: int
    start_position: tuple[float, float]
    end_position: tuple[float, float]
    max_speed_kmh: float
    distance_m: float


@dataclass
class AnalyticsResult:
    """Complete analytics result for a tracked entity.

    Attributes:
        total_distance_km: Total distance traveled in kilometers.
        max_speed_kmh: Maximum instantaneous speed in km/h.
        avg_speed_kmh: Average speed in km/h.
        sprint_segments: List of sprint segments (speed > threshold).
        route_points: List of (field_x, field_y, timestamp_s) tuples.
    """

    total_distance_km: float = 0.0
    max_speed_kmh: float = 0.0
    avg_speed_kmh: float = 0.0
    sprint_segments: list[SprintSegment] = field(default_factory=list)
    route_points: list[tuple[float, float, float]] = field(default_factory=list)


class AnalyticsEngine:
    """Computes performance metrics from track histories.

    Takes track positions in field coordinates (meters) and video FPS
    to compute distances, speeds, and sprint segments.

    Args:
        fps: Video frames per second for time calculations.
        sprint_threshold_kmh: Speed threshold to classify as sprinting.
        speed_window: Number of frames for sliding window speed calculation.
    """

    def __init__(
        self,
        fps: float = 30.0,
        sprint_threshold_kmh: float = 20.0,
        speed_window: int = 3,
    ):
        if fps <= 0:
            raise ValueError("FPS must be positive")
        self.fps = fps
        self.sprint_threshold_kmh = sprint_threshold_kmh
        self.speed_window = speed_window

    def compute(
        self, positions: list[tuple[float, float, int]]
    ) -> AnalyticsResult:
        """Compute analytics from a track field-coordinate history.

        Args:
            positions: List of (field_x, field_y, frame_num) tuples.

        Returns:
            AnalyticsResult with computed metrics.
        """
        if len(positions) < 2:
            route_pts = []
            if positions:
                x, y, frame = positions[0]
                route_pts = [(x, y, frame / self.fps)]
            return AnalyticsResult(
                total_distance_km=0.0,
                max_speed_kmh=0.0,
                avg_speed_kmh=0.0,
                sprint_segments=[],
                route_points=route_pts,
            )

        distances = []
        speeds = []
        route_points = []

        for i, (x, y, frame) in enumerate(positions):
            timestamp = frame / self.fps
            route_points.append((x, y, timestamp))

            if i > 0:
                prev_x, prev_y, prev_frame = positions[i - 1]
                dist_m = math.sqrt((x - prev_x) ** 2 + (y - prev_y) ** 2)
                distances.append(dist_m)

                frame_diff = frame - prev_frame
                if frame_diff > 0:
                    time_s = frame_diff / self.fps
                    speed_ms = dist_m / time_s
                    speed_kmh = speed_ms * 3.6
                else:
                    speed_kmh = 0.0

                speeds.append(speed_kmh)

        total_distance_km = sum(distances) / 1000.0

        total_frames = positions[-1][2] - positions[0][2]
        total_time_s = total_frames / self.fps if total_frames > 0 else 0.0
        avg_speed_kmh = (
            (total_distance_km / (total_time_s / 3600.0))
            if total_time_s > 0
            else 0.0
        )

        max_speed_kmh = 0.0
        if speeds:
            if len(speeds) >= self.speed_window:
                for i in range(len(speeds) - self.speed_window + 1):
                    window = speeds[i : i + self.speed_window]
                    window_avg = sum(window) / len(window)
                    max_speed_kmh = max(max_speed_kmh, window_avg)
            else:
                max_speed_kmh = max(speeds)

        sprint_segments = self._detect_sprints(positions, speeds)

        return AnalyticsResult(
            total_distance_km=total_distance_km,
            max_speed_kmh=max_speed_kmh,
            avg_speed_kmh=avg_speed_kmh,
            sprint_segments=sprint_segments,
            route_points=route_points,
        )

    def _detect_sprints(
        self,
        positions: list[tuple[float, float, int]],
        speeds: list[float],
    ) -> list[SprintSegment]:
        """Detect sprint segments where speed exceeds the threshold."""
        segments = []
        in_sprint = False
        sprint_start_idx = 0
        sprint_max_speed = 0.0
        sprint_distance = 0.0

        for i, speed in enumerate(speeds):
            if speed >= self.sprint_threshold_kmh:
                if not in_sprint:
                    in_sprint = True
                    sprint_start_idx = i
                    sprint_max_speed = speed
                    sprint_distance = 0.0
                else:
                    sprint_max_speed = max(sprint_max_speed, speed)

                prev_x, prev_y, _ = positions[i]
                cur_x, cur_y, _ = positions[i + 1]
                sprint_distance += math.sqrt(
                    (cur_x - prev_x) ** 2 + (cur_y - prev_y) ** 2
                )
            else:
                if in_sprint:
                    start_pos = positions[sprint_start_idx]
                    end_pos = positions[i]
                    segments.append(
                        SprintSegment(
                            start_frame=start_pos[2],
                            end_frame=end_pos[2],
                            start_position=(start_pos[0], start_pos[1]),
                            end_position=(end_pos[0], end_pos[1]),
                            max_speed_kmh=sprint_max_speed,
                            distance_m=sprint_distance,
                        )
                    )
                    in_sprint = False

        if in_sprint:
            start_pos = positions[sprint_start_idx]
            end_pos = positions[-1]
            segments.append(
                SprintSegment(
                    start_frame=start_pos[2],
                    end_frame=end_pos[2],
                    start_position=(start_pos[0], start_pos[1]),
                    end_position=(end_pos[0], end_pos[1]),
                    max_speed_kmh=sprint_max_speed,
                    distance_m=sprint_distance,
                )
            )

        return segments
