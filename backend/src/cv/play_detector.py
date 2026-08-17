"""Rugby play detection engine.

Detects rugby plays (tackles, scrums, rucks, line-outs, trys) from
player movement patterns including speed, convergence, and clustering.
"""

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

        # Get all unique timestamps across all players
        all_timestamps = self._get_all_timestamps(player_routes)

        # Check each pair of players for convergence at high speed
        player_ids = list(player_routes.keys())
        for i, j in combinations(range(len(player_ids)), 2):
            pid_a = player_ids[i]
            pid_b = player_ids[j]
            route_a = player_routes[pid_a]
            route_b = player_routes[pid_b]

            # Find timestamps where both players have data
            times_a = {pt["timestamp"] for pt in route_a}
            times_b = {pt["timestamp"] for pt in route_b}
            common_times = sorted(times_a & times_b)

            for t in common_times:
                pt_a = self._get_point_at_time(route_a, t)
                pt_b = self._get_point_at_time(route_b, t)

                if pt_a is None or pt_b is None:
                    continue

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
                        route_a, route_b, t, self.TACKLE_TIME_WINDOW_S
                    )
                    if converging:
                        mid_x = (pt_a["x"] + pt_b["x"]) / 2
                        mid_y = (pt_a["y"] + pt_b["y"]) / 2
                        confidence = min(
                            1.0,
                            (max(speed_a, speed_b) / self.TACKLE_SPEED_THRESHOLD_KMH)
                            * (1.0 - dist / self.TACKLE_DISTANCE_THRESHOLD_M)
                        )
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

            for pid, route in player_routes.items():
                pt = self._get_point_at_time(route, t)
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
                        play_type="line-out",
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
                play_type="line-out",
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

        all_timestamps = self._get_common_timestamps(player_routes)

        window_start: float | None = None
        window_players: list[str] = []
        window_centroid: tuple[float, float] = (0.0, 0.0)

        for t in all_timestamps:
            # Get positions and speeds at this timestamp
            current_positions: list[tuple[str, float, float, float]] = []

            for pid, route in player_routes.items():
                pt = self._get_point_at_time(route, t)
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

    def _get_point_at_time(
        self, route: list[dict[str, Any]], timestamp: float
    ) -> dict[str, Any] | None:
        """Get the route point at exact timestamp, or None."""
        for pt in route:
            if abs(pt.get("timestamp", -1) - timestamp) < 0.001:
                return pt
        return None

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
        route_a: list[dict[str, Any]],
        route_b: list[dict[str, Any]],
        current_time: float,
        window: float,
    ) -> bool:
        """Check if two players were converging within the time window.

        Returns True if the distance between them was larger earlier
        in the window than it is at current_time.
        """
        # Get current distance
        pt_a_now = self._get_point_at_time(route_a, current_time)
        pt_b_now = self._get_point_at_time(route_b, current_time)
        if pt_a_now is None or pt_b_now is None:
            return False

        dist_now = self._distance(
            pt_a_now["x"], pt_a_now["y"], pt_b_now["x"], pt_b_now["y"]
        )

        # Look for an earlier time within the window
        earlier_time = current_time - window
        # Find closest available point before the window
        best_a = None
        best_b = None
        for pt in route_a:
            t = pt.get("timestamp", 0)
            if earlier_time - 0.5 <= t <= current_time - 0.01:
                if best_a is None or abs(t - earlier_time) < abs(best_a.get("timestamp", 0) - earlier_time):
                    best_a = pt

        for pt in route_b:
            t = pt.get("timestamp", 0)
            if earlier_time - 0.5 <= t <= current_time - 0.01:
                if best_b is None or abs(t - earlier_time) < abs(best_b.get("timestamp", 0) - earlier_time):
                    best_b = pt

        if best_a is None or best_b is None:
            # If there's no earlier point, consider it convergence
            # (they appeared close already)
            return True

        dist_earlier = self._distance(
            best_a["x"], best_a["y"], best_b["x"], best_b["y"]
        )

        # Converging if distance decreased
        return dist_earlier > dist_now

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
