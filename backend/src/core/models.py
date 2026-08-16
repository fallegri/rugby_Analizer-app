"""Core domain models for the Rugby Analyzer system."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.core.enums import AnalysisStatus, TrackingMode, VideoStatus


class Video(BaseModel):
    """Represents an uploaded video for analysis."""

    id: UUID = Field(default_factory=uuid4)
    filename: str
    status: VideoStatus = VideoStatus.UPLOADED
    duration: Optional[float] = None
    resolution: Optional[tuple[int, int]] = None
    fps: Optional[float] = None
    file_path: Optional[str] = None


class PlayerSelection(BaseModel):
    """Represents a player selected for tracking."""

    player_id: str
    bounding_box: tuple[float, float, float, float] = Field(
        description="Bounding box as (x, y, width, height)"
    )
    team: Optional[str] = None
    label: Optional[str] = None


class FieldCalibration(BaseModel):
    """Represents the field calibration data for coordinate mapping."""

    points: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Reference points on the field (pixel coordinates)",
    )
    homography_matrix: Optional[list[list[float]]] = None
    auto_detected: bool = False


class AnalysisRequest(BaseModel):
    """Request to start a video analysis session."""

    video_id: UUID
    mode: TrackingMode
    players: list[PlayerSelection] = Field(default_factory=list)
    calibration: Optional[FieldCalibration] = None


class TrackingResult(BaseModel):
    """Results from a tracking analysis session."""

    routes: list[list[tuple[float, float]]] = Field(
        default_factory=list,
        description="List of routes (each route is a list of (x, y) positions)",
    )
    max_speed: Optional[float] = Field(None, description="Maximum speed in km/h")
    avg_speed: Optional[float] = Field(None, description="Average speed in km/h")
    total_distance: Optional[float] = Field(None, description="Total distance in km")
    positions: list[dict] = Field(
        default_factory=list,
        description="Frame-by-frame position data",
    )
    heatmap_data: Optional[list[list[float]]] = None


class TrackingSession(BaseModel):
    """Represents an active or completed tracking session."""

    id: UUID = Field(default_factory=uuid4)
    video_id: UUID
    mode: TrackingMode
    target_players: list[str] = Field(default_factory=list)
    status: AnalysisStatus = AnalysisStatus.PENDING
    result: Optional[TrackingResult] = None
    error_message: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
