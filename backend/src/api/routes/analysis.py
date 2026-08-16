"""Analysis orchestration API endpoints.

Provides endpoints for starting analysis, checking status,
retrieving results, and querying AI about analysis data.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.core.enums import AnalysisStatus, TrackingMode
from src.core.models import AnalysisRequest, FieldCalibration, PlayerSelection
from src.services.analysis_service import AnalysisService

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
async def start_analysis(request: StartAnalysisRequest) -> dict[str, str]:
    """Start a new analysis session.

    Creates a session, validates the request, and initiates
    background processing.

    Args:
        request: Analysis configuration.

    Returns:
        Dict with session_id.

    Raises:
        HTTPException: If video_id is invalid.
    """
    service = get_analysis_service()

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
    return {"session_id": session_id}


@router.get("/{session_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(session_id: str) -> AnalysisStatusResponse:
    """Get the current status of an analysis session.

    Args:
        session_id: The analysis session UUID.

    Returns:
        Current progress information.

    Raises:
        HTTPException: If session not found.
    """
    service = get_analysis_service()

    try:
        status_data = service.get_status(session_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    return AnalysisStatusResponse(**status_data)


@router.get("/{session_id}/results", response_model=AnalysisResultsResponse)
async def get_analysis_results(session_id: str) -> AnalysisResultsResponse:
    """Get completed analysis results.

    Args:
        session_id: The analysis session UUID.

    Returns:
        Full analysis results.

    Raises:
        HTTPException: If session not found or not complete.
    """
    service = get_analysis_service()

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


@router.post("/{session_id}/ai-query", response_model=AIQueryResponse)
async def ai_query(session_id: str, request: AIQueryRequest) -> AIQueryResponse:
    """Query AI about analysis results with context injection.

    Retrieves analysis data and injects it as context into the
    AI prompt for contextual responses.

    Args:
        session_id: The analysis session UUID.
        request: The AI query (prompt).

    Returns:
        AI response with context indication.

    Raises:
        HTTPException: If session not found or AI provider unavailable.
    """
    service = get_analysis_service()

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

    # For now, return a placeholder response since AI providers
    # need real API keys to function. In production, this calls the AI provider.
    response_text = (
        f"Analysis query received for session {session_id}. "
        f"Prompt: {request.prompt}"
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
