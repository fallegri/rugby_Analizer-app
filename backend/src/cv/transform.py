"""Coordinate transformation between pixel and field space.

Maps pixel coordinates from video frames to real-world rugby field coordinates
in meters. Supports:
- HomographyTransform: 3x3 homography matrix from point correspondences
- LinearFieldTransform: Simple linear mapping from a play area rectangle
- DefaultFieldTransform: Assumes visible frame covers approximately 60m x 40m
"""

from dataclasses import dataclass
from typing import Optional, Protocol

import cv2
import numpy as np


# Rugby field dimensions in meters
FIELD_LENGTH_M = 100.0
FIELD_WIDTH_M = 70.0

# Default visible field area (typical broadcast camera view)
DEFAULT_VISIBLE_LENGTH_M = 60.0
DEFAULT_VISIBLE_WIDTH_M = 40.0


class FieldTransform(Protocol):
    """Protocol for any coordinate transform from pixel to field space."""

    def pixel_to_field(self, x: float, y: float) -> tuple[float, float]:
        """Transform pixel coordinates to field coordinates."""
        ...


class DefaultFieldTransform:
    """Default pixel-to-field transform when no calibration is available.

    Assumes the visible video frame covers approximately 60m x 40m of the field,
    centered around the midfield area. Linearly maps pixel coordinates to field
    meters.

    Args:
        frame_width: Video frame width in pixels.
        frame_height: Video frame height in pixels.
        field_length: Assumed visible field length in meters (default 60m).
        field_width: Assumed visible field width in meters (default 40m).
        field_offset_x: X offset on the field in meters (default 20m, centering 60m view on 100m field).
        field_offset_y: Y offset on the field in meters (default 15m, centering 40m view on 70m field).
    """

    def __init__(
        self,
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
        field_length: float = DEFAULT_VISIBLE_LENGTH_M,
        field_width: float = DEFAULT_VISIBLE_WIDTH_M,
        field_offset_x: float = 20.0,
        field_offset_y: float = 15.0,
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.field_length = field_length
        self.field_width = field_width
        self.field_offset_x = field_offset_x
        self.field_offset_y = field_offset_y

    def pixel_to_field(self, x: float, y: float) -> tuple[float, float]:
        """Transform pixel coordinates to field coordinates.

        Maps pixel (x, y) linearly to a region of the field.

        Args:
            x: Pixel X coordinate.
            y: Pixel Y coordinate.

        Returns:
            Tuple of (field_x, field_y) in meters, clamped to field bounds.
        """
        fx = (x / self.frame_width) * self.field_length + self.field_offset_x
        fy = (y / self.frame_height) * self.field_width + self.field_offset_y

        # Clamp to valid field bounds
        fx = max(0.0, min(FIELD_LENGTH_M, fx))
        fy = max(0.0, min(FIELD_WIDTH_M, fy))

        return (fx, fy)


class LinearFieldTransform:
    """Linear pixel-to-field transform based on a user-defined play area.

    The user draws a rectangle on the 2D field diagram indicating which part
    of the field is visible in the video. This transform linearly maps pixel
    coordinates to that field region.

    Args:
        frame_width: Video frame width in pixels.
        frame_height: Video frame height in pixels.
        field_x_min: Left edge of the play area on the field (meters, 0-100).
        field_x_max: Right edge of the play area on the field (meters, 0-100).
        field_y_min: Top edge of the play area on the field (meters, 0-70).
        field_y_max: Bottom edge of the play area on the field (meters, 0-70).
    """

    def __init__(
        self,
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
        field_x_min: float = 20.0,
        field_x_max: float = 80.0,
        field_y_min: float = 10.0,
        field_y_max: float = 60.0,
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.field_x_min = field_x_min
        self.field_x_max = field_x_max
        self.field_y_min = field_y_min
        self.field_y_max = field_y_max

    def pixel_to_field(self, x: float, y: float) -> tuple[float, float]:
        """Transform pixel coordinates to field coordinates.

        Linearly maps pixels to the user-defined field rectangle.

        Args:
            x: Pixel X coordinate.
            y: Pixel Y coordinate.

        Returns:
            Tuple of (field_x, field_y) in meters, clamped to field bounds.
        """
        fx = (x / self.frame_width) * (self.field_x_max - self.field_x_min) + self.field_x_min
        fy = (y / self.frame_height) * (self.field_y_max - self.field_y_min) + self.field_y_min

        # Clamp to valid field bounds
        fx = max(0.0, min(FIELD_LENGTH_M, fx))
        fy = max(0.0, min(FIELD_WIDTH_M, fy))

        return (fx, fy)


@dataclass
class PointCorrespondence:
    """A pixel-to-field coordinate mapping point.

    Attributes:
        pixel_x: X coordinate in pixel space.
        pixel_y: Y coordinate in pixel space.
        field_x: X coordinate in field space (meters along length, 0-100).
        field_y: Y coordinate in field space (meters along width, 0-70).
    """

    pixel_x: float
    pixel_y: float
    field_x: float
    field_y: float


class HomographyTransform:
    """Transforms coordinates between pixel space and field space using homography.

    Stores a 3x3 homography matrix and provides methods to transform
    points and trajectories between coordinate systems.

    Args:
        matrix: 3x3 homography matrix (pixel -> field).
        validate_bounds: Whether to clamp output to field bounds.
    """

    def __init__(self, matrix: np.ndarray, validate_bounds: bool = True):
        if matrix.shape != (3, 3):
            raise ValueError(f"Homography matrix must be 3x3, got {matrix.shape}")
        self.matrix = matrix.astype(np.float64)
        self.validate_bounds = validate_bounds
        self._inverse_matrix = np.linalg.inv(self.matrix)

    def pixel_to_field(self, x: float, y: float) -> tuple[float, float]:
        """Transform pixel coordinates to field coordinates.

        Args:
            x: Pixel X coordinate.
            y: Pixel Y coordinate.

        Returns:
            Tuple of (field_x, field_y) in meters.
        """
        point = np.array([[[x, y]]], dtype=np.float64)
        transformed = cv2.perspectiveTransform(point, self.matrix)
        field_x = float(transformed[0, 0, 0])
        field_y = float(transformed[0, 0, 1])

        if self.validate_bounds:
            field_x = max(0.0, min(FIELD_LENGTH_M, field_x))
            field_y = max(0.0, min(FIELD_WIDTH_M, field_y))

        return (field_x, field_y)

    def field_to_pixel(self, fx: float, fy: float) -> tuple[float, float]:
        """Transform field coordinates to pixel coordinates.

        Args:
            fx: Field X coordinate in meters (0-100).
            fy: Field Y coordinate in meters (0-70).

        Returns:
            Tuple of (pixel_x, pixel_y).
        """
        point = np.array([[[fx, fy]]], dtype=np.float64)
        transformed = cv2.perspectiveTransform(point, self._inverse_matrix)
        px = float(transformed[0, 0, 0])
        py = float(transformed[0, 0, 1])
        return (px, py)

    def transform_trajectory(
        self, points: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Transform a list of pixel coordinates to field coordinates.

        Args:
            points: List of (pixel_x, pixel_y) tuples.

        Returns:
            List of (field_x, field_y) tuples in meters.
        """
        if not points:
            return []

        pts_array = np.array([[list(p) for p in points]], dtype=np.float64)
        transformed = cv2.perspectiveTransform(pts_array, self.matrix)

        result = []
        for i in range(transformed.shape[1]):
            fx = float(transformed[0, i, 0])
            fy = float(transformed[0, i, 1])

            if self.validate_bounds:
                fx = max(0.0, min(FIELD_LENGTH_M, fx))
                fy = max(0.0, min(FIELD_WIDTH_M, fy))

            result.append((fx, fy))

        return result

    def to_list(self) -> list[list[float]]:
        """Serialize the homography matrix to a nested list."""
        return self.matrix.tolist()

    @classmethod
    def from_list(cls, matrix_list: list[list[float]], validate_bounds: bool = True) -> "HomographyTransform":
        """Create a HomographyTransform from a nested list.

        Args:
            matrix_list: 3x3 matrix as nested lists.
            validate_bounds: Whether to validate output bounds.

        Returns:
            HomographyTransform instance.
        """
        matrix = np.array(matrix_list, dtype=np.float64)
        return cls(matrix, validate_bounds=validate_bounds)
