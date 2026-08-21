"""Team classification by dominant jersey color.

Analyzes the dominant color within player bounding boxes to classify
players into team_a or team_b. Supports manual team color specification
or automatic detection via K-means clustering.

Once team colors are determined, classification uses a fast Euclidean
distance metric on the mean upper-body color (no per-frame K-means).
K-means is only used during auto-detection and dominant color caching.
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

    After team colors are determined, classification uses a fast mean-color
    approach with Euclidean distance instead of per-frame K-means, caching
    the dominant color per track and re-classifying every N frames.

    Args:
        team_a_color: RGB tuple for team A jersey color (optional).
        team_b_color: RGB tuple for team B jersey color (optional).
        auto_detect: Whether to auto-detect team colors if not provided.
        reclassify_interval: Number of frames between re-classification per track.
    """

    # Minimum number of distinct player samples required before committing
    # to auto-detected team colors. Prevents unreliable clustering when
    # early frames contain very few players.
    MIN_SAMPLES_FOR_DETECTION = 10

    def __init__(
        self,
        team_a_color: Optional[tuple[int, int, int]] = None,
        team_b_color: Optional[tuple[int, int, int]] = None,
        auto_detect: bool = True,
        reclassify_interval: int = 30,
    ):
        self.team_a_color = team_a_color
        self.team_b_color = team_b_color
        self.auto_detect = auto_detect
        self._colors_detected = team_a_color is not None and team_b_color is not None
        self._detection_samples: list[tuple[int, int, int]] = []
        self._detection_frames_needed = 5
        self._detection_frame_count = 0
        # Cache: track_id -> (dominant_color, last_classified_frame)
        self._track_color_cache: dict[int, tuple[tuple[int, int, int], int]] = {}
        self._reclassify_interval = reclassify_interval

    def classify_player(
        self, frame: np.ndarray, bbox: tuple, track_id: Optional[int] = None, frame_num: int = 0
    ) -> Optional[str]:
        """Classify a player's team based on their jersey color.

        Uses a fast mean-color approach once team colors are known. The dominant
        color per track is cached and only recomputed every reclassify_interval
        frames to avoid expensive per-frame K-means.

        Args:
            frame: Full video frame as numpy array (BGR).
            bbox: Bounding box as (x1, y1, x2, y2).
            track_id: Optional track ID for caching dominant colors.
            frame_num: Current frame number for cache invalidation.

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

        # Use cached color if available and fresh
        dominant = None
        if track_id is not None and track_id in self._track_color_cache:
            cached_color, cached_frame = self._track_color_cache[track_id]
            if frame_num - cached_frame < self._reclassify_interval:
                dominant = cached_color

        if dominant is None:
            # Use fast mean-color approach (no K-means on hot path)
            dominant = self._get_mean_color(crop)
            if dominant is not None and track_id is not None:
                self._track_color_cache[track_id] = (dominant, frame_num)

        if dominant is None:
            return None

        # Compare to team colors using Euclidean distance in RGB space
        dist_a = np.sqrt(sum((int(a) - int(b)) ** 2 for a, b in zip(dominant, self.team_a_color)))  # type: ignore[arg-type]
        dist_b = np.sqrt(sum((int(a) - int(b)) ** 2 for a, b in zip(dominant, self.team_b_color)))  # type: ignore[arg-type]

        # Require a minimum difference to classify confidently
        if abs(dist_a - dist_b) < 15:
            return None

        return "team_a" if dist_a < dist_b else "team_b"

    def _get_mean_color(
        self, image_crop: np.ndarray
    ) -> Optional[tuple[int, int, int]]:
        """Extract the mean non-green color from an image crop (fast path).

        Computes the mean RGB color of the crop after filtering out green
        (field) pixels. Much faster than K-means for per-frame classification.

        Args:
            image_crop: BGR image crop (numpy array).

        Returns:
            Mean color as RGB tuple, or None if the crop is too small.
        """
        if image_crop.size == 0 or image_crop.shape[0] < 1 or image_crop.shape[1] < 1:
            return None

        # Convert to RGB
        rgb = cv2.cvtColor(image_crop, cv2.COLOR_BGR2RGB)
        pixels = rgb.reshape(-1, 3).astype(np.float32)

        if len(pixels) < 3:
            return None

        # Filter out green (field) pixels
        r, g, b = pixels[:, 0], pixels[:, 1], pixels[:, 2]
        non_green_mask = ~((g > 80) & (g > r * 1.3) & (g > b * 1.3))

        non_green_pixels = pixels[non_green_mask]
        if len(non_green_pixels) < 3:
            # All pixels are green, return overall mean
            mean = pixels.mean(axis=0)
            return (int(mean[0]), int(mean[1]), int(mean[2]))

        mean = non_green_pixels.mean(axis=0)
        return (int(mean[0]), int(mean[1]), int(mean[2]))

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

        if self._detection_frame_count >= self._detection_frames_needed and len(self._detection_samples) >= self.MIN_SAMPLES_FOR_DETECTION:
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
