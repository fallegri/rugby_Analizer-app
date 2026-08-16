"""Video management API endpoints.

Handles video upload, metadata retrieval, processing initiation,
results retrieval, and video deletion.
"""

import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.config.settings import get_settings
from src.core.enums import TrackingMode, VideoStatus

router = APIRouter(prefix="/api/video", tags=["video"])

# In-memory storage (replace with database in production)
_videos: dict[str, dict] = {}

# Allowed video file extensions
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


class VideoMetadata(BaseModel):
    """Response model for video metadata."""

    id: str
    filename: str
    status: VideoStatus
    file_path: Optional[str] = None
    size_bytes: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[tuple[int, int]] = None


class ProcessRequest(BaseModel):
    """Request body for starting video processing."""

    mode: TrackingMode
    target_ids: list[int] = Field(default_factory=list)
    calibration_id: Optional[str] = None
    calibration_points: Optional[list[dict]] = None


class ProcessingResult(BaseModel):
    """Response model for analysis results."""

    video_id: str
    status: str
    total_frames: Optional[int] = None
    fps: Optional[float] = None
    duration_s: Optional[float] = None
    analytics: Optional[dict] = None


@router.post("/upload", response_model=VideoMetadata, status_code=status.HTTP_201_CREATED)
async def upload_video(file: UploadFile = File(...)) -> VideoMetadata:
    """Upload a video file for analysis."""
    settings = get_settings()

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Allowed: mp4, avi, mov, mkv",
        )

    content = await file.read()
    size_bytes = len(content)

    max_size = settings.max_file_size_mb * 1024 * 1024
    if size_bytes > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_bytes} bytes) exceeds maximum ({max_size} bytes)",
        )

    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    video_id = str(uuid4())
    safe_filename = f"{video_id}{ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    video_data = {
        "id": video_id,
        "filename": file.filename,
        "status": VideoStatus.UPLOADED,
        "file_path": file_path,
        "size_bytes": size_bytes,
        "duration": None,
        "fps": None,
        "resolution": None,
    }
    _videos[video_id] = video_data

    return VideoMetadata(**video_data)


@router.get("/{video_id}", response_model=VideoMetadata)
async def get_video(video_id: str) -> VideoMetadata:
    """Get video metadata and status."""
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )

    return VideoMetadata(**_videos[video_id])


@router.post("/{video_id}/process", response_model=ProcessingResult)
async def process_video(video_id: str, request: ProcessRequest) -> ProcessingResult:
    """Start processing a video with the specified tracking mode."""
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )

    video = _videos[video_id]

    if video["status"] not in (VideoStatus.UPLOADED, VideoStatus.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video cannot be reprocessed in current state",
        )

    video["status"] = VideoStatus.ANALYZING

    return ProcessingResult(
        video_id=video_id,
        status=VideoStatus.ANALYZING.value,
        total_frames=None,
        fps=None,
        duration_s=None,
        analytics=None,
    )


@router.get("/{video_id}/results", response_model=ProcessingResult)
async def get_results(video_id: str) -> ProcessingResult:
    """Get analysis results for a processed video."""
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )

    video = _videos[video_id]
    vid_status = video["status"].value if isinstance(video["status"], VideoStatus) else video["status"]

    return ProcessingResult(
        video_id=video_id,
        status=vid_status,
        total_frames=video.get("total_frames"),
        fps=video.get("fps"),
        duration_s=video.get("duration_s"),
        analytics=video.get("analytics"),
    )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: str) -> None:
    """Delete a video and its associated data."""
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )

    video = _videos[video_id]

    file_path = video.get("file_path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    del _videos[video_id]
