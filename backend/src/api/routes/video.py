"""Video management API endpoints.

Handles video upload, metadata retrieval, processing initiation,
results retrieval, video streaming, and video deletion.
"""

import logging
import os
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.security import sanitize_filename, validate_file_upload
from src.config.settings import get_settings
from src.core.enums import TrackingMode, VideoStatus

logger = logging.getLogger(__name__)

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
    target_player_ids: Optional[list[str]] = Field(default=None)
    calibration_id: Optional[str] = None
    calibration_points: Optional[list[dict]] = None
    calibration: Optional[dict] = None
    play_area: Optional[dict] = None
    player_selections: Optional[list[dict]] = None


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


@router.post("/{video_id}/process")
async def process_video(video_id: str, request: ProcessRequest, req: Request) -> dict[str, str]:
    """Start processing a video with the specified tracking mode.

    Instantiates the full CV pipeline (YOLODetector, MultiObjectTracker,
    TrackingStrategy, AnalyticsEngine), starts background processing,
    and returns a session_id for WebSocket progress tracking.

    Args:
        video_id: UUID of the video to process.
        request: Processing configuration (mode, targets, calibration).
        req: FastAPI request for accessing app state.

    Returns:
        Dict with session_id for WebSocket progress tracking.

    Raises:
        HTTPException: If video is not found, not in processable state,
                       or CV pipeline instantiation fails.
    """
    if video_id not in _videos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video = _videos[video_id]

    # Allow re-processing from any state except if the video file is missing.
    # If currently ANALYZING, reset to allow a fresh run.
    if video["status"] == VideoStatus.ANALYZING:
        logger.info(
            f"Video {video_id} is currently ANALYZING - resetting for re-processing"
        )
        video["status"] = VideoStatus.UPLOADED

    # Update status to processing
    video["status"] = VideoStatus.ANALYZING

    # Get services from app state
    analysis_service = req.app.state.analysis_service
    background_task_manager = req.app.state.background_task_manager

    # Create an analysis session
    from src.core.models import AnalysisRequest as DomainAnalysisRequest

    try:
        video_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video_id format",
        )

    domain_request = DomainAnalysisRequest(
        video_id=video_uuid,
        mode=request.mode,
        players=[],
        calibration=None,
    )

    session_id = analysis_service.start_analysis(domain_request)

    video_path = video.get("file_path")
    if not video_path:
        analysis_service.mark_failed(session_id, "Video file path not found")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video file path not found on server",
        )

    from src.api.websocket import manager as ws_manager

    # Instantiate the CV pipeline
    video_processor = None
    instantiation_error = None
    try:
        from src.cv.detector import YOLODetector
        from src.cv.tracker import MultiObjectTracker
        from src.cv.tracking_modes import (
            BallCarrierStrategy,
            BallOnlyStrategy,
            GroupTrackingStrategy,
            SinglePlayerStrategy,
        )
        from src.cv.analytics import AnalyticsEngine

        logger.info(
            f"[Session {session_id}] Initializing CV pipeline | "
            f"Mode: {request.mode.value} | Video: {video_path}"
        )

        # Create detector with YOLOv8n (lightweight, GTX 1060 compatible)
        detector = YOLODetector(
            model_path="yolov8n.pt",
            confidence_threshold=0.25,
            device="auto",
        )

        # Create ByteTrack-style tracker
        tracker = MultiObjectTracker(
            iou_threshold=0.3,
            max_age=30,
            min_hits=3,
        )

        # Select tracking strategy based on mode
        strategy_map = {
            TrackingMode.SINGLE_PLAYER: SinglePlayerStrategy,
            TrackingMode.BALL_CARRIER: BallCarrierStrategy,
            TrackingMode.BALL_ONLY: BallOnlyStrategy,
            TrackingMode.GROUP_TRACKING: GroupTrackingStrategy,
        }
        strategy_class = strategy_map.get(request.mode, SinglePlayerStrategy)
        tracking_strategy = strategy_class()

        # Create analytics engine (FPS will be updated during processing)
        analytics_engine = AnalyticsEngine(fps=30.0)

        # Handle calibration-based homography transform
        from src.cv.video_processor import VideoProcessor

        transform = None
        calibration_data = request.calibration

        # Priority 1: play_area calibration (user draws rectangle on field diagram)
        if request.play_area and isinstance(request.play_area, dict):
            try:
                from src.cv.transform import LinearFieldTransform

                field_x_min = float(request.play_area.get("x_min", 20.0))
                field_x_max = float(request.play_area.get("x_max", 80.0))
                field_y_min = float(request.play_area.get("y_min", 10.0))
                field_y_max = float(request.play_area.get("y_max", 60.0))

                transform = LinearFieldTransform(
                    frame_width=1920.0,
                    frame_height=1080.0,
                    field_x_min=field_x_min,
                    field_x_max=field_x_max,
                    field_y_min=field_y_min,
                    field_y_max=field_y_max,
                )
                logger.info(
                    f"[Session {session_id}] PlayArea transform initialized: "
                    f"x=[{field_x_min}, {field_x_max}] y=[{field_y_min}, {field_y_max}]"
                )
            except Exception as pa_err:
                logger.warning(
                    f"[Session {session_id}] Could not create PlayArea transform: {pa_err}. "
                    f"Will use default transform."
                )

        # Priority 2: point-based homography calibration
        elif calibration_data and isinstance(calibration_data, dict):
            cal_points = calibration_data.get("points")
            if cal_points and len(cal_points) >= 4:
                try:
                    from src.cv.transform import HomographyTransform
                    import numpy as np
                    import cv2

                    src_pts = np.array(
                        [[p.get("pixel_x", p[0] if isinstance(p, (list, tuple)) else 0),
                          p.get("pixel_y", p[1] if isinstance(p, (list, tuple)) else 0)]
                         for p in cal_points[:4]],
                        dtype=np.float64,
                    )
                    dst_pts = np.array(
                        [[p.get("field_x", p[2] if isinstance(p, (list, tuple)) else 0),
                          p.get("field_y", p[3] if isinstance(p, (list, tuple)) else 0)]
                         for p in cal_points[:4]],
                        dtype=np.float64,
                    )
                    matrix, _ = cv2.findHomography(src_pts, dst_pts)
                    if matrix is not None:
                        transform = HomographyTransform(matrix)
                        logger.info(f"[Session {session_id}] Homography transform initialized")
                except Exception as cal_err:
                    logger.warning(
                        f"[Session {session_id}] Could not compute homography: {cal_err}. "
                        f"Will use default transform."
                    )

        # Extract player selection bounding boxes for target acquisition
        player_selection_boxes = []
        if request.player_selections:
            for sel in request.player_selections:
                if isinstance(sel, dict) and "x" in sel and "y" in sel:
                    player_selection_boxes.append({
                        "x": float(sel.get("x", 0)),
                        "y": float(sel.get("y", 0)),
                        "width": float(sel.get("width", 0)),
                        "height": float(sel.get("height", 0)),
                    })

        video_processor = VideoProcessor(
            detector=detector,
            tracker=tracker,
            transform=transform,
            tracking_strategy=tracking_strategy,
            analytics_engine=analytics_engine,
            player_selection_boxes=player_selection_boxes,
        )
        logger.info(f"[Session {session_id}] CV pipeline initialized successfully")

    except Exception as e:
        instantiation_error = str(e)
        logger.error(
            f"[Session {session_id}] Failed to initialize CV pipeline: {instantiation_error}",
            exc_info=True,
        )

    # If instantiation failed, report error immediately
    if instantiation_error and video_processor is None:
        analysis_service.mark_failed(
            session_id, f"CV pipeline initialization failed: {instantiation_error}"
        )
        # Send error via WebSocket so frontend knows immediately
        await ws_manager.send_message(
            session_id,
            {
                "type": "error",
                "session_id": session_id,
                "error": f"No se pudo inicializar el procesador de video: {instantiation_error}",
            },
        )
        # Still return session_id so frontend can display the error state
        return {"session_id": session_id}

    # Build target IDs from both possible request fields
    target_ids: list[int] = list(request.target_ids) if request.target_ids else []
    if request.target_player_ids:
        for pid in request.target_player_ids:
            try:
                target_ids.append(int(pid))
            except (ValueError, TypeError):
                pass

    # Start background processing
    await background_task_manager.start_processing(
        session_id=session_id,
        video_path=video_path,
        mode=request.mode.value,
        target_ids=target_ids,
        analysis_service=analysis_service,
        ws_manager=ws_manager,
        video_processor=video_processor,
    )

    logger.info(
        f"[Session {session_id}] Background processing started | "
        f"Video: {video_id} | Mode: {request.mode.value}"
    )

    return {"session_id": session_id}


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
