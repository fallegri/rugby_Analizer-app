"""Rugby play detection engine.

Detects rugby plays (tackles, scrums, rucks, line-outs, trys) from
player movement patterns including speed, convergence, and clustering.
"""

import bisect
import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any


@dataclass
class DetectedPlay:
    """A detected rugby play event."""

    play_type: str
    start_time: float
    end_time: float
    confidence: float
    players_involved: list[str]
    position: tuple[float, float]
    description: str
    ai_explanation: str | None = None


class PlayDetector:
    """Detects rugby plays from player movement data.

    Analyzes route points (x, y, timestamp, speed) for each player to
    identify common rugby play patterns: tackles, scrums, rucks,
    line-outs, and trys.
    """

    # Detection thresholds
    TACKLE_SPEED_THRESHOLD_KMH = 15.0
    TACKLE_DISTANCE_THRESHOLD_M = 2.0
    TACKLE_TIME_WINDOW_S = 0.5

    SCRUM_MIN_PLAYERS = 8
    SCRUM_RADIUS_M = 5.0
    SCRUM_MAX_SPEED_KMH = 3.0
    SCRUM_MIN_DURATION_S = 3.0

    RUCK_MIN_PLAYERS = 3
    RUCK_MAX_PLAYERS = 6
    RUCK_RADIUS_M = 3.0
    RUCK_MAX_SPEED_KMH = 3.0
    RUCK_MIN_DURATION_S = 2.0

    LINEOUT_MIN_PLAYERS = 4
    LINEOUT_SIDELINE_Y_LOW = 5.0
    LINEOUT_SIDELINE_Y_HIGH = 63.0
    LINEOUT_MAX_SPEED_KMH = 3.0
    LINEOUT_MIN_DURATION_S = 2.0

    TRY_LINE_X_HIGH = 95.0
    TRY_LINE_X_LOW = 5.0
    TRY_SPEED_THRESHOLD_KMH = 10.0

    def detect_plays(self, players_data: list[dict[str, Any]]) -> list[DetectedPlay]:
        """Detect all rugby plays from player movement data.

        Args:
            players_data: List of player dicts, each with:
                - player_id: str
                - route: list of {x, y, timestamp, speed}
                - total_distance_km, max_speed_kmh, avg_speed_kmh
                - sprint_count, sprints

        Returns:
            List of DetectedPlay instances sorted by start_time.
        """
        if not players_data:
            return []

        plays: list[DetectedPlay] = []

        plays.extend(self._detect_tackles(players_data))
        plays.extend(self._detect_scrums(players_data))
        plays.extend(self._detect_rucks(players_data))
        plays.extend(self._detect_lineouts(players_data))
        plays.extend(self._detect_trys(players_data))

        # Cross-type deduplication: suppress lower-confidence plays of
        # different types that overlap in time and space (e.g., a ruck
        # and scrum detected for the same physical event)
        plays = self._deduplicate_cross_type(plays, time_threshold=2.0, dist_threshold=5.0)

        # Sort by start_time
        plays.sort(key=lambda p: p.start_time)
        return plays

    def _detect_tackles(self, players_data: list[dict[str, Any]]) -> list[DetectedPlay]:
        """Detect tackles: 2+ players converging rapidly with close proximity."""
        plays: list[DetectedPlay] = []

        # Build time-indexed positions for all players
        player_routes = self._build_player_routes(players_data)

        if len(player_routes) < 2:
            return plays

        # Build O(1) time indexes and sorted key lists for each player route
        player_time_indexes: dict[str, dict[float, dict[str, Any]]] = {}
        player_sorted_keys: dict[str, list[float]] = {}
        for pid, route in player_routes.items():
            index = self._build_time_index(route)
            player_time_indexes[pid] = index
            player_sorted_keys[pid] = sorted(index.keys())

        # Check each pair of players for convergence at high speed
        player_ids = list(player_routes.keys())
        for i, j in combinations(range(len(player_ids)), 2):
            pid_a = player_ids[i]
            pid_b = player_ids[j]
            index_a = player_time_indexes[pid_a]
            index_b = player_time_indexes[pid_b]
            keys_a = player_sorted_keys[pid_a]
            keys_b = player_sorted_keys[pid_b]

            # Find timestamps where both players have data
            times_a = set(index_a.keys())
            times_b = set(index_b.keys())
            common_times = sorted(times_a & times_b)

            for t in common_times:
                pt_a = index_a[t]
                pt_b = index_b[t]

                dist = self._distance(pt_a["x"], pt_a["y"], pt_b["x"], pt_b["y"])
                speed_a = pt_a["speed"]
                speed_b = pt_b["speed"]

                # Check if both are moving fast and are close
                if (
                    dist < self.TACKLE_DISTANCE_THRESHOLD_M
                    and (speed_a > self.TACKLE_SPEED_THRESHOLD_KMH
                         or speed_b > self.TACKLE_SPEED_THRESHOLD_KMH)
                    and max(speed_a, speed_b) > self.TACKLE_SPEED_THRESHOLD_KMH
                ):
                    # Check convergence: were they farther apart in a recent window?
                    converging = self._check_convergence(
                        index_a, index_b, keys_a, keys_b, t, self.TACKLE_TIME_WINDOW_S
                    )
                    if converging:
                        mid_x = (pt_a["x"] + pt_b["x"]) / 2
                        mid_y = (pt_a["y"] + pt_b["y"]) / 2
                        confidence = min(
                            1.0,
                            (max(speed_a, speed_b) / self.TACKLE_SPEED_THRESHOLD_KMH)
                            * (1.0 - dist / self.TACKLE_DISTANCE_THRESHOLD_M)
                        )

                        # Boost confidence if posture data confirms tackle posture
                        keypoints_a = pt_a.get("keypoints")
                        keypoints_b = pt_b.get("keypoints")
                        if keypoints_a and self._is_tackle_posture(keypoints_a):
                            confidence = min(1.0, confidence * 1.3)
                        if keypoints_b and self._is_tackle_posture(keypoints_b):
                            confidence = min(1.0, confidence * 1.3)

                        plays.append(DetectedPlay(
                            play_type="tackle",
                            start_time=max(0.0, t - self.TACKLE_TIME_WINDOW_S),
                            end_time=t,
                            confidence=max(0.1, confidence),
                            players_involved=[pid_a, pid_b],
                            position=(mid_x, mid_y),
                            description=(
                                f"Tackle detected: players {pid_a} and {pid_b} "
                                f"converged at high speed ({max(speed_a, speed_b):.1f} km/h) "
                                f"within {dist:.1f}m"
                            ),
                        ))

        # Deduplicate tackles that are very close in time and position
        plays = self._deduplicate_plays(plays, time_threshold=1.0, dist_threshold=3.0)
        return plays

    def _detect_scrums(self, players_data: list[dict[str, Any]]) -> list[DetectedPlay]:
        """Detect scrums: 8+ players clustered tightly with low speed for > 3s."""
        return self._detect_cluster_play(
            players_data,
            play_type="scrum",
            min_players=self.SCRUM_MIN_PLAYERS,
            max_players=None,
            radius_threshold=self.SCRUM_RADIUS_M,
            max_speed_kmh=self.SCRUM_MAX_SPEED_KMH,
            min_duration_s=self.SCRUM_MIN_DURATION_S,
            description_template="Scrum detected: {count} players clustered within {radius:.1f}m radius",
        )

    def _detect_rucks(self, players_data: list[dict[str, Any]]) -> list[DetectedPlay]:
        """Detect rucks: 3-6 players clustered with low speed for > 2s."""
        return self._detect_cluster_play(
            players_data,
            play_type="ruck",
            min_players=self.RUCK_MIN_PLAYERS,
            max_players=self.RUCK_MAX_PLAYERS,
            radius_threshold=self.RUCK_RADIUS_M,
            max_speed_kmh=self.RUCK_MAX_SPEED_KMH,
            min_duration_s=self.RUCK_MIN_DURATION_S,
            description_template="Ruck detected: {count} players clustered within {radius:.1f}m radius",
        )

    def _detect_lineouts(self, players_data: list[dict[str, Any]]) -> list[DetectedPlay]:
        """Detect line-outs: 4+ players near sideline in linear formation."""
        plays: list[DetectedPlay] = []
        player_routes = self._build_player_routes(players_data)

        if len(player_routes) < self.LINEOUT_MIN_PLAYERS:
            return plays

        # Build time indexes for O(1) lookups
        player_time_indexes: dict[str, dict[float, dict[str, Any]]] = {}
        for pid, route in player_routes.items():
            player_time_indexes[pid] = self._build_time_index(route)

        # Get all unique timestamps
        all_timestamps = self._get_common_timestamps(player_routes)

        # Sliding window approach
        window_start = None
        window_players: list[str] = []
        window_positions: list[tuple[float, float]] = []

        for t in all_timestamps:
            # Find players near sideline at this timestamp
            sideline_players = []
            positions = []
            rounded_t = round(t, 3)

            for pid, index in player_time_indexes.items():
                pt = index.get(rounded_t)
                if pt is None:
                    continue
                # Check if near sideline
                if (pt["y"] < self.LINEOUT_SIDELINE_Y_LOW
                        or pt["y"] > self.LINEOUT_SIDELINE_Y_HIGH):
                    if pt["speed"] < self.LINEOUT_MAX_SPEED_KMH:
                        sideline_players.append(pid)
                        positions.append((pt["x"], pt["y"]))

            if len(sideline_players) >= self.LINEOUT_MIN_PLAYERS:
                if window_start is None:
                    window_start = t
                window_players = sideline_players
                window_positions = positions
            else:
                if (
                    window_start is not None
                    and (t - window_start) >= self.LINEOUT_MIN_DURATION_S
                    and len(window_players) >= self.LINEOUT_MIN_PLAYERS
                ):
                    centroid = self._centroid(window_positions)
                    plays.append(DetectedPlay(
                        play_type="lineout",
                        start_time=window_start,
                        end_time=t,
                        confidence=min(1.0, len(window_players) / 7.0),
                        players_involved=window_players,
                        position=centroid,
                        description=(
                            f"Line-out detected: {len(window_players)} players "
                            f"near sideline in formation"
                        ),
                    ))
                window_start = None
                window_players = []
                window_positions = []

        # Check if window extends to end
        if (
            window_start is not None
            and all_timestamps
            and (all_timestamps[-1] - window_start) >= self.LINEOUT_MIN_DURATION_S
            and len(window_players) >= self.LINEOUT_MIN_PLAYERS
        ):
            centroid = self._centroid(window_positions)
            plays.append(DetectedPlay(
                play_type="lineout",
                start_time=window_start,
                end_time=all_timestamps[-1],
                confidence=min(1.0, len(window_players) / 7.0),
                players_involved=window_players,
                position=centroid,
                description=(
                    f"Line-out detected: {len(window_players)} players "
                    f"near sideline in formation"
                ),
            ))

        return self._deduplicate_plays(plays, time_threshold=2.0, dist_threshold=5.0)

    def _detect_trys(self, players_data: list[dict[str, Any]]) -> list[DetectedPlay]:
        """Detect trys: player crossing try line at significant speed."""
        plays: list[DetectedPlay] = []

        for player in players_data:
            pid = str(player.get("player_id", ""))
            route = player.get("route", [])

            for i in range(1, len(route)):
                prev_pt = route[i - 1]
                curr_pt = route[i]

                x = curr_pt.get("x", 0)
                prev_x = prev_pt.get("x", 0)
                speed = curr_pt.get("speed", 0)
                timestamp = curr_pt.get("timestamp", 0)

                # Check crossing try line at high end
                if (
                    x > self.TRY_LINE_X_HIGH
                    and prev_x <= self.TRY_LINE_X_HIGH
                    and speed > self.TRY_SPEED_THRESHOLD_KMH
                ):
                    confidence = min(1.0, speed / (self.TRY_SPEED_THRESHOLD_KMH * 2))
                    plays.append(DetectedPlay(
                        play_type="try",
                        start_time=prev_pt.get("timestamp", 0),
                        end_time=timestamp,
                        confidence=confidence,
                        players_involved=[pid],
                        position=(x, curr_pt.get("y", 0)),
                        description=(
                            f"Try detected: player {pid} crossed try line "
                            f"at {speed:.1f} km/h"
                        ),
                    ))

                # Check crossing try line at low end
                if (
                    x < self.TRY_LINE_X_LOW
                    and prev_x >= self.TRY_LINE_X_LOW
                    and speed > self.TRY_SPEED_THRESHOLD_KMH
                ):
                    confidence = min(1.0, speed / (self.TRY_SPEED_THRESHOLD_KMH * 2))
                    plays.append(DetectedPlay(
                        play_type="try",
                        start_time=prev_pt.get("timestamp", 0),
                        end_time=timestamp,
                        confidence=confidence,
                        players_involved=[pid],
                        position=(x, curr_pt.get("y", 0)),
                        description=(
                            f"Try detected: player {pid} crossed try line "
                            f"at {speed:.1f} km/h"
                        ),
                    ))

        return plays

    def _detect_cluster_play(
        self,
        players_data: list[dict[str, Any]],
        play_type: str,
        min_players: int,
        max_players: int | None,
        radius_threshold: float,
        max_speed_kmh: float,
        min_duration_s: float,
        description_template: str,
    ) -> list[DetectedPlay]:
        """Generic cluster-based play detection (scrums, rucks)."""
        plays: list[DetectedPlay] = []
        player_routes = self._build_player_routes(players_data)

        if len(player_routes) < min_players:
            return plays

        # Build time indexes for O(1) lookups
        player_time_indexes: dict[str, dict[float, dict[str, Any]]] = {}
        for pid, route in player_routes.items():
            player_time_indexes[pid] = self._build_time_index(route)

        all_timestamps = self._get_common_timestamps(player_routes)

        window_start: float | None = None
        window_players: list[str] = []
        window_centroid: tuple[float, float] = (0.0, 0.0)

        for t in all_timestamps:
            # Get positions and speeds at this timestamp
            current_positions: list[tuple[str, float, float, float]] = []
            rounded_t = round(t, 3)

            for pid, index in player_time_indexes.items():
                pt = index.get(rounded_t)
                if pt is not None:
                    current_positions.append((pid, pt["x"], pt["y"], pt["speed"]))

            # Filter to low-speed players
            low_speed_players = [
                (pid, x, y, s) for pid, x, y, s in current_positions
                if s < max_speed_kmh
            ]

            # Find the largest cluster among low-speed players
            cluster = self._find_largest_cluster(
                low_speed_players, radius_threshold
            )

            cluster_count = len(cluster)
            meets_min = cluster_count >= min_players
            meets_max = max_players is None or cluster_count <= max_players

            if meets_min and meets_max:
                if window_start is None:
                    window_start = t
                cluster_pids = [pid for pid, _, _, _ in cluster]
                cluster_positions = [(x, y) for _, x, y, _ in cluster]
                window_players = cluster_pids
                window_centroid = self._centroid(cluster_positions)
            else:
                if (
                    window_start is not None
                    and (t - window_start) >= min_duration_s
                ):
                    radius = self._max_radius_from_centroid(
                        [(x, y) for _, x, y, _ in
                         self._find_largest_cluster(
                             [(pid, x, y, s) for pid, x, y, s in current_positions
                              if s < max_speed_kmh],
                             radius_threshold
                         )],
                        window_centroid
                    ) if current_positions else 0.0

                    plays.append(DetectedPlay(
                        play_type=play_type,
                        start_time=window_start,
                        end_time=t,
                        confidence=min(1.0, len(window_players) / (min_players + 2)),
                        players_involved=window_players,
                        position=window_centroid,
                        description=description_template.format(
                            count=len(window_players),
                            radius=radius_threshold,
                        ),
                    ))
                window_start = None
                window_players = []

        # Check if window extends to end of data
        if (
            window_start is not None
            and all_timestamps
            and (all_timestamps[-1] - window_start) >= min_duration_s
        ):
            plays.append(DetectedPlay(
                play_type=play_type,
                start_time=window_start,
                end_time=all_timestamps[-1],
                confidence=min(1.0, len(window_players) / (min_players + 2)),
                players_involved=window_players,
                position=window_centroid,
                description=description_template.format(
                    count=len(window_players),
                    radius=radius_threshold,
                ),
            ))

        return self._deduplicate_plays(plays, time_threshold=2.0, dist_threshold=5.0)

    # --- Helper methods ---

    def _build_player_routes(
        self, players_data: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Build a dict mapping player_id to their route points."""
        routes: dict[str, list[dict[str, Any]]] = {}
        for player in players_data:
            pid = str(player.get("player_id", ""))
            route = player.get("route", [])
            if route:
                routes[pid] = route
        return routes

    def _get_all_timestamps(
        self, player_routes: dict[str, list[dict[str, Any]]]
    ) -> list[float]:
        """Get all unique timestamps across all players, sorted."""
        timestamps: set[float] = set()
        for route in player_routes.values():
            for pt in route:
                timestamps.add(pt.get("timestamp", 0))
        return sorted(timestamps)

    def _get_common_timestamps(
        self, player_routes: dict[str, list[dict[str, Any]]]
    ) -> list[float]:
        """Get all unique timestamps across all players, sorted."""
        return self._get_all_timestamps(player_routes)

    def _build_time_index(
        self, route: list[dict[str, Any]]
    ) -> dict[float, dict[str, Any]]:
        """Build a timestamp -> point index for O(1) lookups.

        Rounds timestamps to 3 decimal places for consistent matching.
        """
        index: dict[float, dict[str, Any]] = {}
        for pt in route:
            t = round(pt.get("timestamp", -1), 3)
            index[t] = pt
        return index

    def _get_point_at_time(
        self, route: list[dict[str, Any]], timestamp: float
    ) -> dict[str, Any] | None:
        """Get the route point at exact timestamp, or None.

        Falls back to linear scan for compatibility when no index is provided.
        """
        rounded_t = round(timestamp, 3)
        for pt in route:
            if round(pt.get("timestamp", -1), 3) == rounded_t:
                return pt
        return None

    def _get_point_from_index(
        self, index: dict[float, dict[str, Any]], timestamp: float
    ) -> dict[str, Any] | None:
        """O(1) point lookup using a pre-built time index."""
        return index.get(round(timestamp, 3))

    def _distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """Euclidean distance between two points."""
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def _centroid(self, positions: list[tuple[float, float]]) -> tuple[float, float]:
        """Compute centroid of a list of (x, y) positions."""
        if not positions:
            return (0.0, 0.0)
        avg_x = sum(p[0] for p in positions) / len(positions)
        avg_y = sum(p[1] for p in positions) / len(positions)
        return (avg_x, avg_y)

    def _max_radius_from_centroid(
        self, positions: list[tuple[float, float]], centroid: tuple[float, float]
    ) -> float:
        """Max distance from centroid to any point."""
        if not positions:
            return 0.0
        return max(
            self._distance(centroid[0], centroid[1], x, y)
            for x, y in positions
        )

    def _find_largest_cluster(
        self,
        players: list[tuple[str, float, float, float]],
        radius: float,
    ) -> list[tuple[str, float, float, float]]:
        """Find the largest cluster of players within the given radius.

        Uses a simple greedy approach: for each player, count how many
        others are within radius of that player. Return the largest group.
        """
        if not players:
            return []

        best_cluster: list[tuple[str, float, float, float]] = []

        for i, (pid_i, xi, yi, si) in enumerate(players):
            cluster = [(pid_i, xi, yi, si)]
            for j, (pid_j, xj, yj, sj) in enumerate(players):
                if i == j:
                    continue
                if self._distance(xi, yi, xj, yj) <= radius:
                    cluster.append((pid_j, xj, yj, sj))

            if len(cluster) > len(best_cluster):
                best_cluster = cluster

        return best_cluster

    def _check_convergence(
        self,
        index_a: dict[float, dict[str, Any]],
        index_b: dict[float, dict[str, Any]],
        sorted_keys_a: list[float],
        sorted_keys_b: list[float],
        current_time: float,
        window: float,
    ) -> bool:
        """Check if two players were converging within the time window.

        Uses pre-built time indexes with sorted keys and bisect for
        O(log n) earlier-point lookups instead of linear scans.

        Returns True if the distance between them was larger earlier
        in the window than it is at current_time.
        """
        # Get current distance using O(1) index lookup
        pt_a_now = self._get_point_from_index(index_a, current_time)
        pt_b_now = self._get_point_from_index(index_b, current_time)
        if pt_a_now is None or pt_b_now is None:
            return False

        dist_now = self._distance(
            pt_a_now["x"], pt_a_now["y"], pt_b_now["x"], pt_b_now["y"]
        )

        # Look for an earlier time within the window
        earlier_time = current_time - window

        # Use bisect on sorted keys to find the closest point in the window
        best_a = self._find_nearest_point_in_window(
            index_a, sorted_keys_a, earlier_time - 0.5, current_time - 0.01, earlier_time
        )
        best_b = self._find_nearest_point_in_window(
            index_b, sorted_keys_b, earlier_time - 0.5, current_time - 0.01, earlier_time
        )

        if best_a is None or best_b is None:
            # If there's no earlier point, consider it convergence
            # (they appeared close already)
            return True

        dist_earlier = self._distance(
            best_a["x"], best_a["y"], best_b["x"], best_b["y"]
        )

        # Converging if distance decreased
        return dist_earlier > dist_now

    def _find_nearest_point_in_window(
        self,
        index: dict[float, dict[str, Any]],
        sorted_keys: list[float],
        window_start: float,
        window_end: float,
        target_time: float,
    ) -> dict[str, Any] | None:
        """Find the point in the time index closest to target_time within [window_start, window_end].

        Uses bisect on pre-sorted keys for O(log n) lookup.
        """
        # Find the insertion point for window_start
        left = bisect.bisect_left(sorted_keys, window_start)
        # Find the insertion point for window_end
        right = bisect.bisect_right(sorted_keys, window_end)

        if left >= right:
            return None

        # Search only within the valid window range for the closest to target_time
        best_key = None
        best_diff = float("inf")
        for i in range(left, right):
            key = sorted_keys[i]
            diff = abs(key - target_time)
            if diff < best_diff:
                best_diff = diff
                best_key = key

        if best_key is None:
            return None
        return index[best_key]

    def _is_tackle_posture(self, keypoints: list) -> bool:
        """Check if keypoints indicate a tackle posture (low/diving position).

        Analyzes the shoulder-hip line angle relative to vertical.
        A player in tackle posture has their torso angled more than 45 degrees
        from vertical (leaning forward or diving).

        Args:
            keypoints: List of (x, y, confidence) tuples for 17 COCO keypoints.

        Returns:
            True if the posture indicates a tackle (torso angle > 45 degrees).
        """
        if not keypoints or len(keypoints) < 13:
            return False

        # COCO indices: 5=left_shoulder, 6=right_shoulder, 11=left_hip, 12=right_hip
        left_shoulder = keypoints[5] if len(keypoints) > 5 else None
        right_shoulder = keypoints[6] if len(keypoints) > 6 else None
        left_hip = keypoints[11] if len(keypoints) > 11 else None
        right_hip = keypoints[12] if len(keypoints) > 12 else None

        # Need at least one shoulder and one hip with sufficient confidence
        min_conf = 0.3

        shoulder_x, shoulder_y = None, None
        if left_shoulder and left_shoulder[2] >= min_conf:
            shoulder_x, shoulder_y = left_shoulder[0], left_shoulder[1]
        if right_shoulder and right_shoulder[2] >= min_conf:
            if shoulder_x is None:
                shoulder_x, shoulder_y = right_shoulder[0], right_shoulder[1]
            else:
                # Average both shoulders for midpoint
                shoulder_x = (shoulder_x + right_shoulder[0]) / 2
                shoulder_y = (shoulder_y + right_shoulder[1]) / 2

        hip_x, hip_y = None, None
        if left_hip and left_hip[2] >= min_conf:
            hip_x, hip_y = left_hip[0], left_hip[1]
        if right_hip and right_hip[2] >= min_conf:
            if hip_x is None:
                hip_x, hip_y = right_hip[0], right_hip[1]
            else:
                hip_x = (hip_x + right_hip[0]) / 2
                hip_y = (hip_y + right_hip[1]) / 2

        if shoulder_x is None or hip_x is None:
            return False

        # Compute angle of torso from vertical
        # In image coordinates, y increases downward, so hip is usually below shoulder
        dx = shoulder_x - hip_x
        dy = shoulder_y - hip_y  # negative when shoulder is above hip (normal standing)

        # Angle from vertical (0 = standing upright, 90 = horizontal)
        torso_length = math.sqrt(dx * dx + dy * dy)
        if torso_length < 1.0:
            return False

        # Angle from vertical: use atan2 of horizontal displacement vs vertical
        angle_from_vertical = math.degrees(math.atan2(abs(dx), abs(dy)))

        # Tackle posture: torso angled > 45 degrees from vertical
        return angle_from_vertical > 45.0

    def _deduplicate_plays(
        self,
        plays: list[DetectedPlay],
        time_threshold: float,
        dist_threshold: float,
    ) -> list[DetectedPlay]:
        """Remove duplicate plays that are very close in time and space."""
        if not plays:
            return plays

        unique: list[DetectedPlay] = []
        for play in plays:
            is_dup = False
            for existing in unique:
                if existing.play_type != play.play_type:
                    continue
                time_diff = abs(play.start_time - existing.start_time)
                pos_diff = self._distance(
                    play.position[0], play.position[1],
                    existing.position[0], existing.position[1],
                )
                if time_diff < time_threshold and pos_diff < dist_threshold:
                    # Keep the one with higher confidence
                    if play.confidence > existing.confidence:
                        unique.remove(existing)
                        unique.append(play)
                    is_dup = True
                    break
            if not is_dup:
                unique.append(play)

        return unique

    def _deduplicate_cross_type(
        self,
        plays: list[DetectedPlay],
        time_threshold: float,
        dist_threshold: float,
    ) -> list[DetectedPlay]:
        """Remove overlapping plays of different types for the same event.

        When two cluster-based plays (ruck, scrum) overlap in time and
        space with shared players, the one with higher confidence is kept.
        This handles cases like a ruck and scrum being detected for the
        same physical event without suppressing unrelated detections.
        """
        if not plays:
            return plays

        # Only apply cross-type dedup between cluster-based play types
        # that can genuinely overlap for the same physical event
        cluster_types = {"ruck", "scrum"}

        # Sort by confidence descending so higher-confidence plays are kept
        sorted_plays = sorted(plays, key=lambda p: p.confidence, reverse=True)
        kept: list[DetectedPlay] = []

        for play in sorted_plays:
            is_suppressed = False
            for existing in kept:
                # Only cross-type dedup between cluster-based types
                if existing.play_type == play.play_type:
                    continue
                if play.play_type not in cluster_types or existing.play_type not in cluster_types:
                    continue
                # Check time overlap
                time_overlap = (
                    play.start_time <= existing.end_time
                    and play.end_time >= existing.start_time
                )
                if not time_overlap:
                    continue
                # Check spatial proximity
                pos_diff = self._distance(
                    play.position[0], play.position[1],
                    existing.position[0], existing.position[1],
                )
                if pos_diff < dist_threshold:
                    # Check player overlap - at least one shared player
                    shared_players = set(play.players_involved) & set(existing.players_involved)
                    if shared_players:
                        # The existing play has higher confidence (sorted order)
                        is_suppressed = True
                        break
            if not is_suppressed:
                kept.append(play)

        return kept
