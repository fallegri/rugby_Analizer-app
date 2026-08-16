"""Video management API endpoints.

Handles video upload, metadata retrieval, processing initiation,
results retrieval, video streaming, and video deletion.
"""

import os
import shutil
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.security import sanitize_filename, validate_file_upload
from src.config.settings import get_settings
from src.core.enums import TrackingMode, VideoStatus

router = APIRouter(prefix="/api/video", tags=["video"])

# In-memory storage (replace with database in production)
# TODO: MVP limitation - all video metadata is stored in-memory and lost on restart.
# For production, persist to SQLite/Postgres via the repository pattern.
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
    """Upload a video file for analysis.

    Validates file format, magic bytes, and size, saves to the uploads directory,
    and returns video metadata.

    Args:
        file: Multipart file upload.

    Returns:
        VideoMetadata with the saved video information.

    Raises:
        HTTPException: If file format is invalid or file is too large.
    """
    settings = get_settings()

    # Validate filename is present
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Sanitize filename
    safe_name = sanitize_filename(file.filename)

    # Validate extension
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    # Security validation (magic bytes, size, content type)
    is_valid, error_msg = validate_file_upload(
        content=content,
        filename=safe_name,
        content_type=file.content_type,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Create upload directory
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    # Save file with unique name
    video_id = str(uuid4())
    safe_filename = f"{video_id}{ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # Store metadata
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
    """Get video metadata and status.

    Args:
        video_id: UUID of the video.

    Returns:
        VideoMetadata for the requested video.

    Raises:
        HTTPException: If video is not found.
    """
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    return VideoMetadata(**_videos[video_id])


@router.post("/{video_id}/process", response_model=ProcessingResult)
async def process_video(video_id: str, request: ProcessRequest) -> ProcessingResult:
    """Start processing a video with the specified tracking mode.

    Args:
        video_id: UUID of the video to process.
        request: Processing configuration (mode, targets, calibration).

    Returns:
        ProcessingResult with initial status.

    Raises:
        HTTPException: If video is not found or not in uploadable state.
    """
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video = _videos[video_id]

    if video["status"] not in (VideoStatus.UPLOADED, VideoStatus.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Video is currently in state '{video['status']}' and cannot be reprocessed",
        )

    # Update status to processing
    video["status"] = VideoStatus.ANALYZING

    # In a real implementation, this would queue a background task
    # For now, return the processing status
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
    """Get analysis results for a processed video.

    Args:
        video_id: UUID of the video.

    Returns:
        ProcessingResult with analysis data.

    Raises:
        HTTPException: If video is not found.
    """
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video = _videos[video_id]

    return ProcessingResult(
        video_id=video_id,
        status=video["status"].value if isinstance(video["status"], VideoStatus) else video["status"],
        total_frames=video.get("total_frames"),
        fps=video.get("fps"),
        duration_s=video.get("duration_s"),
        analytics=video.get("analytics"),
    )


@router.get("/{video_id}/stream")
async def stream_video(video_id: str) -> FileResponse:
    """Stream a video file for playback in the browser.

    Serves the video file with appropriate content-type headers
    for the HTML5 video element. Supports range requests via
    FastAPI's FileResponse.

    Args:
        video_id: UUID of the video to stream.

    Returns:
        FileResponse serving the video file.

    Raises:
        HTTPException: If video is not found or file is missing.
    """
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video = _videos[video_id]
    file_path = video.get("file_path")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file not found on disk for video '{video_id}'",
        )

    # Determine content type based on extension
    ext = os.path.splitext(file_path)[1].lower()
    content_type_map = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
    }
    media_type = content_type_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=video.get("filename", f"{video_id}{ext}"),
    )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: str) -> None:
    """Delete a video and its associated data.

    Args:
        video_id: UUID of the video to delete.

    Raises:
        HTTPException: If video is not found.
    """
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video = _videos[video_id]

    # Delete the file if it exists
    file_path = video.get("file_path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    # Remove from storage
    del _videos[video_id]
