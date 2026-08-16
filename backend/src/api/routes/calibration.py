"""Calibration API endpoints.

Handles automatic and manual field calibration, including
persistence of calibration data for reuse.
"""

from typing import Optional
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.cv.calibration import AutoCalibrator, ManualCalibrator
from src.cv.transform import HomographyTransform, PointCorrespondence

router = APIRouter(prefix="/api/calibration", tags=["calibration"])

# In-memory storage (replace with database in production)
# TODO: MVP limitation - calibrations are stored in-memory and lost on restart.
# For production, persist to SQLite/Postgres via the repository pattern.
_calibrations: dict[str, dict] = {}


class PointCorrespondenceInput(BaseModel):
    """A single pixel-to-field point correspondence."""

    pixel_x: float
    pixel_y: float
    field_x: float
    field_y: float


class ManualCalibrationRequest(BaseModel):
    """Request body for manual calibration."""

    points: list[PointCorrespondenceInput] = Field(
        ..., min_length=4, description="At least 4 point correspondences required"
    )


class AutoCalibrationRequest(BaseModel):
    """Request body for automatic calibration."""

    frame_data: Optional[str] = Field(
        None, description="Base64-encoded frame image"
    )
    video_id: Optional[str] = Field(
        None, description="Video ID to extract frame from"
    )
    frame_number: int = Field(default=0, description="Frame number to use for calibration")


class CalibrationResponse(BaseModel):
    """Response model for calibration data."""

    id: str
    method: str
    homography_matrix: list[list[float]]
    num_points: int
    success: bool
    message: Optional[str] = None


@router.post("/manual", response_model=CalibrationResponse, status_code=status.HTTP_201_CREATED)
async def manual_calibration(request: ManualCalibrationRequest) -> CalibrationResponse:
    """Compute calibration from manual point correspondences."""
    correspondences = [
        PointCorrespondence(
            pixel_x=p.pixel_x,
            pixel_y=p.pixel_y,
            field_x=p.field_x,
            field_y=p.field_y,
        )
        for p in request.points
    ]

    calibrator = ManualCalibrator()
    transform = calibrator.calibrate(correspondences)

    if transform is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not compute homography from provided points.",
        )

    calibration_id = str(uuid4())
    matrix_list = transform.to_list()

    _calibrations[calibration_id] = {
        "id": calibration_id,
        "method": "manual",
        "homography_matrix": matrix_list,
        "num_points": len(request.points),
        "success": True,
    }

    return CalibrationResponse(
        id=calibration_id,
        method="manual",
        homography_matrix=matrix_list,
        num_points=len(request.points),
        success=True,
        message="Manual calibration computed successfully",
    )


@router.post("/auto", response_model=CalibrationResponse, status_code=status.HTTP_201_CREATED)
async def auto_calibration(request: AutoCalibrationRequest) -> CalibrationResponse:
    """Attempt automatic field calibration from a video frame."""
    import base64
    import cv2

    frame = None

    if request.frame_data:
        try:
            img_bytes = base64.b64decode(request.frame_data)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid frame data: {str(e)}",
            )
    elif request.video_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Video frame extraction not yet implemented. Provide frame_data directly.",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either frame_data or video_id must be provided",
        )

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode frame data",
        )

    calibrator = AutoCalibrator()
    transform = calibrator.calibrate(frame)

    if transform is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Automatic calibration failed. Try manual calibration instead.",
        )

    calibration_id = str(uuid4())
    matrix_list = transform.to_list()

    _calibrations[calibration_id] = {
        "id": calibration_id,
        "method": "auto",
        "homography_matrix": matrix_list,
        "num_points": 4,
        "success": True,
    }

    return CalibrationResponse(
        id=calibration_id,
        method="auto",
        homography_matrix=matrix_list,
        num_points=4,
        success=True,
        message="Automatic calibration computed successfully",
    )


@router.get("/{calibration_id}", response_model=CalibrationResponse)
async def get_calibration(calibration_id: str) -> CalibrationResponse:
    """Retrieve a saved calibration by ID."""
    if calibration_id not in _calibrations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Calibration not found: {calibration_id}",
        )

    cal_data = _calibrations[calibration_id]
    return CalibrationResponse(**cal_data)
