"""Field calibration modules for rugby pitch coordinate mapping.

Provides automatic (line-detection based) and manual (point correspondence)
calibration methods to compute homography matrices for pixel-to-field
coordinate transformation.
"""

from typing import Optional

import cv2
import numpy as np

from src.cv.transform import HomographyTransform, PointCorrespondence


# Rugby field geometry constants (meters)
FIELD_LENGTH = 100.0
FIELD_WIDTH = 70.0

# Line markings along length (meters from one try line)
LONGITUDINAL_LINES = [0, 10, 22, 50, 78, 90, 100]

# Line markings along width (meters from one touchline)
LATERAL_LINES = [0, 5, 15, 55, 65, 70]


class AutoCalibrator:
    """Automatic field calibration using line detection.

    Uses Canny edge detection and Hough line transform to detect
    field lines, then matches them to known rugby field geometry
    to compute a homography matrix.

    Args:
        canny_low: Lower threshold for Canny edge detector.
        canny_high: Upper threshold for Canny edge detector.
        hough_threshold: Accumulator threshold for HoughLinesP.
        min_line_length: Minimum line length for HoughLinesP.
        max_line_gap: Maximum gap between line segments for HoughLinesP.
    """

    def __init__(
        self,
        canny_low: int = 50,
        canny_high: int = 150,
        hough_threshold: int = 80,
        min_line_length: int = 100,
        max_line_gap: int = 10,
    ):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap

    def calibrate(self, frame: np.ndarray) -> Optional[HomographyTransform]:
        """Attempt automatic calibration from a video frame.

        Detects field lines and attempts to match them to known rugby
        field geometry. Requires at least 4 intersection points to
        compute a valid homography.

        Args:
            frame: Input frame as numpy array (H, W, C) in BGR format.

        Returns:
            HomographyTransform if calibration succeeds, None otherwise.
        """
        lines = self._detect_lines(frame)
        if lines is None or len(lines) < 4:
            return None

        horizontal_lines, vertical_lines = self._classify_lines(lines)

        if len(horizontal_lines) < 2 or len(vertical_lines) < 2:
            return None

        intersections = self._find_intersections(horizontal_lines, vertical_lines)

        if len(intersections) < 4:
            return None

        correspondences = self._match_to_field_geometry(
            intersections, horizontal_lines, vertical_lines, frame.shape
        )

        if len(correspondences) < 4:
            return None

        src_points = np.array(
            [[c.pixel_x, c.pixel_y] for c in correspondences], dtype=np.float64
        )
        dst_points = np.array(
            [[c.field_x, c.field_y] for c in correspondences], dtype=np.float64
        )

        matrix, mask = cv2.findHomography(src_points, dst_points, cv2.RANSAC, 5.0)

        if matrix is None:
            return None

        return HomographyTransform(matrix)

    def _detect_lines(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Detect lines using Canny + HoughLinesP."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=self.hough_threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap,
        )

        return lines

    def _classify_lines(
        self, lines: np.ndarray
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """Classify lines as horizontal or vertical based on angle."""
        horizontal = []
        vertical = []

        # Handle both (N, 4) and (N, 1, 4) HoughLinesP output formats
        reshaped = lines.reshape(-1, 4)

        for line in reshaped:
            x1, y1, x2, y2 = line
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

            if angle < 30 or angle > 150:
                horizontal.append(line)
            elif 60 < angle < 120:
                vertical.append(line)

        return horizontal, vertical

    def _find_intersections(
        self,
        horizontal_lines: list[np.ndarray],
        vertical_lines: list[np.ndarray],
    ) -> list[tuple[float, float]]:
        """Find intersection points between horizontal and vertical lines."""
        intersections = []

        for h_line in horizontal_lines:
            for v_line in vertical_lines:
                point = self._line_intersection(h_line, v_line)
                if point is not None:
                    intersections.append(point)

        return intersections

    def _line_intersection(
        self, line1: np.ndarray, line2: np.ndarray
    ) -> Optional[tuple[float, float]]:
        """Compute intersection of two line segments (extended to infinity)."""
        x1, y1, x2, y2 = int(line1[0]), int(line1[1]), int(line1[2]), int(line1[3])
        x3, y3, x4, y4 = int(line2[0]), int(line2[1]), int(line2[2]), int(line2[3])

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None

        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom

        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)

        return (float(ix), float(iy))

    def _match_to_field_geometry(
        self,
        intersections: list[tuple[float, float]],
        horizontal_lines: list,
        vertical_lines: list,
        frame_shape: tuple,
    ) -> list[PointCorrespondence]:
        """Match detected intersections to known field line positions."""
        if len(intersections) < 4:
            return []

        points_array = np.array(intersections, dtype=np.float32)

        if len(points_array) < 4:
            return []

        rect = cv2.minAreaRect(points_array)
        box = cv2.boxPoints(rect)

        box_sorted = self._order_points(box)

        field_corners = [
            (0.0, 0.0),
            (FIELD_LENGTH, 0.0),
            (FIELD_LENGTH, FIELD_WIDTH),
            (0.0, FIELD_WIDTH),
        ]

        correspondences = []
        for i, (px, py) in enumerate(box_sorted):
            fx, fy = field_corners[i]
            correspondences.append(
                PointCorrespondence(
                    pixel_x=float(px),
                    pixel_y=float(py),
                    field_x=fx,
                    field_y=fy,
                )
            )

        return correspondences

    def _order_points(self, pts: np.ndarray) -> list[tuple[float, float]]:
        """Order 4 points as: top-left, top-right, bottom-right, bottom-left."""
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).flatten()

        tl = pts[np.argmin(s)]
        br = pts[np.argmax(s)]
        tr = pts[np.argmin(d)]
        bl = pts[np.argmax(d)]

        return [
            (float(tl[0]), float(tl[1])),
            (float(tr[0]), float(tr[1])),
            (float(br[0]), float(br[1])),
            (float(bl[0]), float(bl[1])),
        ]


class ManualCalibrator:
    """Manual field calibration using user-defined point correspondences.

    Accepts at least 4 pixel-to-field coordinate pairs provided by the user
    and computes a homography matrix using RANSAC.
    """

    def calibrate(
        self, correspondences: list[PointCorrespondence]
    ) -> Optional[HomographyTransform]:
        """Compute homography from manual point correspondences.

        Args:
            correspondences: List of at least 4 PointCorrespondence objects.

        Returns:
            HomographyTransform if computation succeeds, None otherwise.

        Raises:
            ValueError: If fewer than 4 correspondences are provided.
        """
        if len(correspondences) < 4:
            raise ValueError(
                f"At least 4 point correspondences required, got {len(correspondences)}"
            )

        src_points = np.array(
            [[c.pixel_x, c.pixel_y] for c in correspondences], dtype=np.float64
        )
        dst_points = np.array(
            [[c.field_x, c.field_y] for c in correspondences], dtype=np.float64
        )

        method = cv2.RANSAC if len(correspondences) > 4 else 0
        matrix, mask = cv2.findHomography(src_points, dst_points, method, 5.0)

        if matrix is None:
            return None

        return HomographyTransform(matrix)
