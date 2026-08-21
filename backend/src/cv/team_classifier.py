"""Team classification by dominant jersey color.

Analyzes the dominant color within player bounding boxes to classify
players into team_a or team_b. Supports manual team color specification
or automatic detection via K-means clustering.
"""

from typing import Optional

import cv2
import numpy as np
from sklearn.cluster import KMeans


class TeamClassifier:
    """Classifies players into teams based on jersey color.

    Uses the upper body region (top 40% of bounding box) to extract
    dominant colors, avoiding shorts and field interference. Can auto-detect
    team colors from the first few frames using K-means clustering.

    Args:
        team_a_color: RGB tuple for team A jersey color (optional).
        team_b_color: RGB tuple for team B jersey color (optional).
        auto_detect: Whether to auto-detect team colors if not provided.
    """

    def __init__(
        self,
        team_a_color: Optional[tuple[int, int, int]] = None,
        team_b_color: Optional[tuple[int, int, int]] = None,
        auto_detect: bool = True,
    ):
        self.team_a_color = team_a_color
        self.team_b_color = team_b_color
        self.auto_detect = auto_detect
        self._colors_detected = team_a_color is not None and team_b_color is not None
        self._detection_samples: list[tuple[int, int, int]] = []
        self._detection_frames_needed = 5
        self._detection_frame_count = 0

    def classify_player(
        self, frame: np.ndarray, bbox: tuple
    ) -> Optional[str]:
        """Classify a player's team based on their jersey color.

        Crops the bounding box from the frame, extracts the dominant color
        from the upper body region (top 40%), converts to HSV for comparison,
        and returns the team assignment.

        Args:
            frame: Full video frame as numpy array (BGR).
            bbox: Bounding box as (x1, y1, x2, y2).

        Returns:
            'team_a', 'team_b', or None if classification is not possible.
        """
        if not self._colors_detected:
            return None

        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        # Validate bounding box
        h, w = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        # Extract upper body region (top 40% of bbox)
        box_height = y2 - y1
        upper_y2 = y1 + int(box_height * 0.4)
        crop = frame[y1:upper_y2, x1:x2]

        if crop.size == 0 or crop.shape[0] < 2 or crop.shape[1] < 2:
            return None

        dominant = self._get_dominant_color(crop)
        if dominant is None:
            return None

        # Compare to team colors using Euclidean distance in RGB space
        dist_a = np.sqrt(sum((int(a) - int(b)) ** 2 for a, b in zip(dominant, self.team_a_color)))  # type: ignore[arg-type]
        dist_b = np.sqrt(sum((int(a) - int(b)) ** 2 for a, b in zip(dominant, self.team_b_color)))  # type: ignore[arg-type]

        # Require a minimum difference to classify confidently
        if abs(dist_a - dist_b) < 15:
            return None

        return "team_a" if dist_a < dist_b else "team_b"

    def auto_detect_teams(
        self, frame: np.ndarray, bboxes: list[tuple]
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """Auto-detect team colors from player bounding boxes using K-means.

        Extracts the dominant color from each player's upper body region,
        then clusters all dominant colors into 2 groups to identify the
        two team colors.

        Args:
            frame: Full video frame as numpy array (BGR).
            bboxes: List of bounding boxes as (x1, y1, x2, y2).

        Returns:
            Tuple of (team_a_color, team_b_color) as RGB tuples.
        """
        colors = []
        h, w = frame.shape[:2]

        for bbox in bboxes:
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            box_height = y2 - y1
            upper_y2 = y1 + int(box_height * 0.4)
            crop = frame[y1:upper_y2, x1:x2]

            if crop.size == 0 or crop.shape[0] < 2 or crop.shape[1] < 2:
                continue

            dominant = self._get_dominant_color(crop)
            if dominant is not None:
                colors.append(dominant)

        if len(colors) < 2:
            # Not enough data, return default colors
            return (255, 0, 0), (0, 0, 255)

        # Cluster dominant colors into 2 groups
        color_array = np.array(colors, dtype=np.float32)
        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        kmeans.fit(color_array)

        centers = kmeans.cluster_centers_
        team_a = tuple(int(c) for c in centers[0])
        team_b = tuple(int(c) for c in centers[1])

        return team_a, team_b  # type: ignore[return-value]

    def collect_detection_sample(
        self, frame: np.ndarray, bboxes: list[tuple]
    ) -> bool:
        """Collect color samples for auto-detection across multiple frames.

        Call this on the first few frames. Once enough samples are collected,
        performs K-means clustering to determine team colors.

        Args:
            frame: Full video frame as numpy array (BGR).
            bboxes: List of bounding boxes as (x1, y1, x2, y2).

        Returns:
            True if team colors have been determined, False if more frames needed.
        """
        if self._colors_detected:
            return True

        h, w = frame.shape[:2]

        for bbox in bboxes:
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            box_height = y2 - y1
            upper_y2 = y1 + int(box_height * 0.4)
            crop = frame[y1:upper_y2, x1:x2]

            if crop.size == 0 or crop.shape[0] < 2 or crop.shape[1] < 2:
                continue

            dominant = self._get_dominant_color(crop)
            if dominant is not None:
                self._detection_samples.append(dominant)

        self._detection_frame_count += 1

        if self._detection_frame_count >= self._detection_frames_needed and len(self._detection_samples) >= 2:
            # Cluster collected samples
            color_array = np.array(self._detection_samples, dtype=np.float32)
            kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
            kmeans.fit(color_array)

            centers = kmeans.cluster_centers_
            self.team_a_color = tuple(int(c) for c in centers[0])  # type: ignore[assignment]
            self.team_b_color = tuple(int(c) for c in centers[1])  # type: ignore[assignment]
            self._colors_detected = True
            return True

        return False

    def _get_dominant_color(
        self, image_crop: np.ndarray
    ) -> Optional[tuple[int, int, int]]:
        """Extract the dominant non-green (non-field) color from an image crop.

        Uses K-means with k=3 to find color clusters, then selects the
        most frequent cluster that is not predominantly green (field color).

        Args:
            image_crop: BGR image crop (numpy array).

        Returns:
            Dominant color as RGB tuple, or None if the crop is too small.
        """
        if image_crop.size == 0 or image_crop.shape[0] < 1 or image_crop.shape[1] < 1:
            return None

        # Resize for faster processing
        resized = cv2.resize(image_crop, (20, 20), interpolation=cv2.INTER_AREA)

        # Reshape to pixel list (RGB, converting from BGR)
        pixels = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pixels_flat = pixels.reshape(-1, 3).astype(np.float32)

        if len(pixels_flat) < 3:
            return None

        # Cluster into 3 colors
        n_clusters = min(3, len(pixels_flat))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        kmeans.fit(pixels_flat)

        # Count pixels per cluster
        labels = kmeans.labels_
        centers = kmeans.cluster_centers_

        # Find the most frequent non-green cluster
        cluster_counts = np.bincount(labels, minlength=n_clusters)

        # Sort clusters by frequency (most frequent first)
        sorted_indices = np.argsort(-cluster_counts)

        for idx in sorted_indices:
            center = centers[idx]
            r, g, b = int(center[0]), int(center[1]), int(center[2])

            # Check if this is predominantly green (field color)
            # A green field pixel has high green, low red/blue
            if g > 80 and g > r * 1.3 and g > b * 1.3:
                continue  # Skip green/field-colored clusters

            return (r, g, b)

        # All clusters are green - unlikely but return the most frequent
        center = centers[sorted_indices[0]]
        return (int(center[0]), int(center[1]), int(center[2]))
