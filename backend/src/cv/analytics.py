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


@dataclass
class RSAResult:
    """Result of Repeated Sprint Ability (RSA) analysis.

    Attributes:
        repeated_sprint_count: Number of sprints that are part of repeated sprint clusters.
        avg_recovery_time_s: Average recovery time between consecutive sprints in clusters.
        max_recovery_time_s: Maximum recovery time between consecutive sprints in clusters.
        min_recovery_time_s: Minimum recovery time between consecutive sprints in clusters.
        speed_degradation_percent: Average percentage speed drop from first to last sprint in clusters.
        sprint_clusters: List of sprint groups where sprints are within the window threshold.
    """

    repeated_sprint_count: int = 0
    avg_recovery_time_s: float = 0.0
    max_recovery_time_s: float = 0.0
    min_recovery_time_s: float = 0.0
    speed_degradation_percent: float = 0.0
    sprint_clusters: list[list[SprintSegment]] = field(default_factory=list)


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

    def compute_rsa(
        self,
        sprint_segments: list[SprintSegment],
        fps: Optional[float] = None,
        window_seconds: float = 30.0,
    ) -> RSAResult:
        """Compute Repeated Sprint Ability (RSA) metrics.

        Groups consecutive sprints where the gap between the end of one sprint
        and the start of the next is less than window_seconds. A cluster with
        2 or more sprints counts as repeated sprints.

        Args:
            sprint_segments: List of SprintSegment objects to analyze.
            fps: Frames per second for time conversion. Defaults to engine fps.
            window_seconds: Maximum gap in seconds between sprints to be
                considered part of the same cluster.

        Returns:
            RSAResult with RSA metrics.
        """
        if fps is None:
            fps = self.fps

        if not sprint_segments or len(sprint_segments) < 2:
            return RSAResult()

        # Sort sprints by start_frame
        sorted_sprints = sorted(sprint_segments, key=lambda s: s.start_frame)

        # Group consecutive sprints into clusters where gap < window_seconds
        clusters: list[list[SprintSegment]] = []
        current_cluster: list[SprintSegment] = [sorted_sprints[0]]

        for i in range(1, len(sorted_sprints)):
            prev_sprint = sorted_sprints[i - 1]
            curr_sprint = sorted_sprints[i]

            # Recovery time = start of next sprint - end of previous sprint
            gap_seconds = (curr_sprint.start_frame - prev_sprint.end_frame) / fps

            if gap_seconds < window_seconds:
                current_cluster.append(curr_sprint)
            else:
                clusters.append(current_cluster)
                current_cluster = [curr_sprint]

        clusters.append(current_cluster)

        # Filter clusters with 2+ sprints (repeated sprints)
        rsa_clusters = [c for c in clusters if len(c) >= 2]

        if not rsa_clusters:
            return RSAResult()

        # Count total repeated sprints
        repeated_sprint_count = sum(len(c) for c in rsa_clusters)

        # Compute recovery times between consecutive sprints in clusters
        recovery_times: list[float] = []
        for cluster in rsa_clusters:
            for i in range(1, len(cluster)):
                recovery = (cluster[i].start_frame - cluster[i - 1].end_frame) / fps
                recovery_times.append(recovery)

        avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 0.0
        max_recovery = max(recovery_times) if recovery_times else 0.0
        min_recovery = min(recovery_times) if recovery_times else 0.0

        # Compute speed degradation: average % drop from first to last sprint in each cluster
        degradations: list[float] = []
        for cluster in rsa_clusters:
            first_speed = cluster[0].max_speed_kmh
            last_speed = cluster[-1].max_speed_kmh
            if first_speed > 0:
                degradation = ((first_speed - last_speed) / first_speed) * 100.0
                degradations.append(degradation)

        speed_degradation_percent = (
            sum(degradations) / len(degradations) if degradations else 0.0
        )

        return RSAResult(
            repeated_sprint_count=repeated_sprint_count,
            avg_recovery_time_s=avg_recovery,
            max_recovery_time_s=max_recovery,
            min_recovery_time_s=min_recovery,
            speed_degradation_percent=speed_degradation_percent,
            sprint_clusters=rsa_clusters,
        )
