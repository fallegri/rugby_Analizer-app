"""Analysis orchestration API endpoints.

Provides endpoints for starting analysis, checking status,
retrieving results, and querying AI about analysis data.
"""

import io
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.enums import AnalysisStatus, TrackingMode
from src.core.models import AnalysisRequest, FieldCalibration, PlayerSelection
from src.services.analysis_service import AnalysisService
from src.services.pdf_report_service import PDFReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Module-level service instance (replaced via dependency injection in app startup)
_analysis_service = AnalysisService()


def get_analysis_service() -> AnalysisService:
    """Get the analysis service instance."""
    return _analysis_service


def set_analysis_service(service: AnalysisService) -> None:
    """Set the analysis service instance (for DI/testing)."""
    global _analysis_service
    _analysis_service = service


class StartAnalysisRequest(BaseModel):
    """Request body for starting an analysis."""

    video_id: str = Field(..., description="UUID of the uploaded video")
    mode: TrackingMode = Field(..., description="Tracking mode to use")
    players: list[dict] = Field(default_factory=list, description="Player selections")
    calibration: Optional[dict] = Field(None, description="Field calibration data")


class AnalysisStatusResponse(BaseModel):
    """Response for analysis status queries."""

    session_id: str
    status: str
    progress: float
    current_frame: int
    total_frames: int


class AnalysisResultsResponse(BaseModel):
    """Response for analysis results."""

    session_id: str
    video_id: str
    mode: str
    status: str
    results: Optional[dict] = None


class AIQueryRequest(BaseModel):
    """Request body for AI analysis queries."""

    prompt: str = Field(..., min_length=1, max_length=5000, description="Analysis question")


class AIQueryResponse(BaseModel):
    """Response for AI analysis queries."""

    session_id: str
    prompt: str
    response: str
    context_used: bool


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_analysis(request: StartAnalysisRequest, req: Request) -> dict[str, str]:
    """Start a new analysis session.

    Creates a session, validates the request, and initiates
    background processing.

    Args:
        request: Analysis configuration.
        req: FastAPI request object for accessing app state.

    Returns:
        Dict with session_id.

    Raises:
        HTTPException: If video_id is invalid.
    """
    service = req.app.state.analysis_service

    # Validate video_id format
    try:
        video_uuid = UUID(request.video_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video_id format. Must be a valid UUID.",
        )

    # Build domain request
    players = []
    for p in request.players:
        if "player_id" in p and "bounding_box" in p:
            players.append(
                PlayerSelection(
                    player_id=p["player_id"],
                    bounding_box=tuple(p["bounding_box"]),
                    team=p.get("team"),
                    label=p.get("label"),
                )
            )

    calibration = None
    if request.calibration and "points" in request.calibration:
        calibration = FieldCalibration(
            points=[tuple(pt) for pt in request.calibration["points"]],
            auto_detected=request.calibration.get("auto_detected", False),
        )

    analysis_request = AnalysisRequest(
        video_id=video_uuid,
        mode=request.mode,
        players=players,
        calibration=calibration,
    )

    session_id = service.start_analysis(analysis_request)

    # Start background processing via the BackgroundTaskManager
    background_task_manager = req.app.state.background_task_manager
    # Look up video path from the video routes in-memory store
    from src.api.routes.video import _videos

    video_data = _videos.get(request.video_id)
    video_path = video_data.get("file_path") if video_data else None

    if video_path:
        from src.api.websocket import manager as ws_manager

        # Instantiate the CV pipeline components
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

            # Assemble the VideoProcessor (transform is optional, requires calibration)
            from src.cv.video_processor import VideoProcessor

            transform = None
            if calibration and calibration.points and len(calibration.points) >= 4:
                try:
                    from src.cv.transform import HomographyTransform
                    import numpy as np
                    import cv2

                    # Build homography from calibration points
                    # Points are (pixel_x, pixel_y, field_x, field_y) tuples
                    src_pts = np.array(
                        [[p[0], p[1]] for p in calibration.points[:4]], dtype=np.float64
                    )
                    dst_pts = np.array(
                        [[p[2], p[3]] for p in calibration.points[:4]], dtype=np.float64
                    )
                    matrix, _ = cv2.findHomography(src_pts, dst_pts)
                    if matrix is not None:
                        transform = HomographyTransform(matrix)
                        logger.info(f"[Session {session_id}] Homography transform initialized from calibration")
                except Exception as cal_err:
                    logger.warning(
                        f"[Session {session_id}] Could not compute homography: {cal_err}. "
                        f"Proceeding without coordinate transform."
                    )

            video_processor = VideoProcessor(
                detector=detector,
                tracker=tracker,
                transform=transform,
                tracking_strategy=tracking_strategy,
                analytics_engine=analytics_engine,
            )
            logger.info(f"[Session {session_id}] CV pipeline initialized successfully")

        except Exception as e:
            instantiation_error = str(e)
            logger.error(
                f"[Session {session_id}] Failed to initialize CV pipeline: {instantiation_error}",
                exc_info=True,
            )

        # If instantiation failed, send error via WebSocket immediately
        if instantiation_error and video_processor is None:
            service.mark_failed(session_id, f"CV pipeline initialization failed: {instantiation_error}")
            await ws_manager.send_message(
                session_id,
                {
                    "type": "error",
                    "session_id": session_id,
                    "error": f"No se pudo inicializar el procesador de video: {instantiation_error}",
                },
            )
            return {"session_id": session_id}

        await background_task_manager.start_processing(
            session_id=session_id,
            video_path=video_path,
            mode=request.mode.value,
            target_ids=[int(p.get("player_id", 0)) for p in request.players if "player_id" in p],
            analysis_service=service,
            ws_manager=ws_manager,
            video_processor=video_processor,
        )

    return {"session_id": session_id}


@router.get("/{session_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(session_id: str, req: Request) -> AnalysisStatusResponse:
    """Get the current status of an analysis session.

    Args:
        session_id: The analysis session UUID.
        req: FastAPI request object for accessing app state.

    Returns:
        Current progress information.

    Raises:
        HTTPException: If session not found.
    """
    service = req.app.state.analysis_service

    try:
        status_data = service.get_status(session_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    return AnalysisStatusResponse(**status_data)


@router.get("/{session_id}/results", response_model=AnalysisResultsResponse)
async def get_analysis_results(session_id: str, req: Request) -> AnalysisResultsResponse:
    """Get completed analysis results.

    Args:
        session_id: The analysis session UUID.
        req: FastAPI request object for accessing app state.

    Returns:
        Full analysis results.

    Raises:
        HTTPException: If session not found or not complete.
    """
    service = req.app.state.analysis_service

    try:
        results = service.get_results(session_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return AnalysisResultsResponse(**results)


@router.get("/{session_id}/export")
async def export_analysis(session_id: str, req: Request) -> dict[str, Any]:
    """Export completed analysis results as a downloadable JSON payload.

    Returns the full analysis data including player metrics, routes,
    speeds, distances, and sprints in a format suitable for download.

    Args:
        session_id: The analysis session UUID.
        req: FastAPI request object for accessing app state.

    Returns:
        Full analysis export data.

    Raises:
        HTTPException: If session not found or not complete.
    """
    service = req.app.state.analysis_service

    try:
        results = service.get_results(session_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Build export payload with all analysis data
    export_data: dict[str, Any] = {
        "session_id": results.get("session_id", session_id),
        "video_id": results.get("video_id", ""),
        "mode": results.get("mode", ""),
        "status": results.get("status", ""),
        "results": results.get("results"),
    }

    return export_data


@router.get("/{session_id}/report/pdf")
async def get_pdf_report(session_id: str, req: Request) -> StreamingResponse:
    """Generate and download a PDF report for the analysis session.

    Args:
        session_id: The analysis session UUID.
        req: FastAPI request object for accessing app state.

    Returns:
        StreamingResponse with PDF content.

    Raises:
        HTTPException: If session not found or not complete.
    """
    service = req.app.state.analysis_service

    try:
        results = service.get_results(session_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    pdf_service = PDFReportService()
    pdf_bytes = pdf_service.generate_report(results)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=rugby_report_{session_id}.pdf"
        },
    )


@router.post("/{session_id}/ai-query", response_model=AIQueryResponse)
async def ai_query(session_id: str, request: AIQueryRequest, req: Request) -> AIQueryResponse:
    """Query AI about analysis results with context injection.

    Retrieves analysis data and injects it as context into the
    AI prompt for contextual responses.

    Args:
        session_id: The analysis session UUID.
        request: The AI query (prompt).
        req: FastAPI request object for accessing app state.

    Returns:
        AI response with context indication.

    Raises:
        HTTPException: If session not found or AI provider unavailable.
    """
    service = req.app.state.analysis_service

    # Verify session exists
    if not service.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    # Try to get results for context (may not be complete yet)
    context_used = False
    context_str = ""

    try:
        results = service.get_results(session_id)
        if results and results.get("results"):
            context_str = _build_ai_context(results)
            context_used = True
    except (KeyError, ValueError):
        # No results available yet - query without context
        pass

    # Build enriched prompt
    enriched_prompt = request.prompt
    if context_str:
        enriched_prompt = (
            f"Analysis Context:\n{context_str}\n\n"
            f"User Question: {request.prompt}"
        )

    # Call the AI provider through the singleton factory
    try:
        provider_factory = req.app.state.provider_factory
        provider = provider_factory.get_provider()

        if not provider.is_configured():
            # Fallback to placeholder if provider is not configured
            response_text = (
                f"AI provider '{provider.get_provider_name()}' is not configured. "
                f"Please set an API key. Query: {request.prompt}"
            )
        else:
            response_text = await provider.analyze_play(enriched_prompt, context_str)
    except Exception as e:
        logger.warning(f"AI provider call failed for session {session_id}: {e}")
        response_text = (
            f"AI analysis unavailable: {str(e)}. "
            f"Query received for session {session_id}: {request.prompt}"
        )

    return AIQueryResponse(
        session_id=session_id,
        prompt=request.prompt,
        response=response_text,
        context_used=context_used,
    )


def _build_ai_context(results: dict[str, Any]) -> str:
    """Build context string from analysis results for AI injection.

    Args:
        results: The analysis results dict.

    Returns:
        Formatted context string for the AI prompt.
    """
    parts = [
        f"Video ID: {results.get('video_id', 'unknown')}",
        f"Tracking Mode: {results.get('mode', 'unknown')}",
    ]

    analysis_data = results.get("results", {})
    if analysis_data:
        parts.append(f"Total Frames: {analysis_data.get('total_frames', 'N/A')}")
        parts.append(f"FPS: {analysis_data.get('fps', 'N/A')}")
        parts.append(f"Duration: {analysis_data.get('duration_s', 'N/A')}s")

        analytics = analysis_data.get("analytics", {})
        if analytics:
            parts.append(f"Tracked entities: {len(analytics)}")
            for track_id, data in analytics.items():
                parts.append(
                    f"  Track {track_id}: "
                    f"max_speed={data.get('max_speed')} km/h, "
                    f"avg_speed={data.get('avg_speed')} km/h, "
                    f"distance={data.get('total_distance')} km"
                )

    return "\n".join(parts)
