"""Play detection API endpoints.

Provides endpoints for detecting and retrieving rugby plays
from completed analysis sessions.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from src.services.play_detection_service import PlayDetectionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["plays"])

# In-memory storage for detected plays per session
_detected_plays: dict[str, list[dict[str, Any]]] = {}

# Service instance
_play_detection_service = PlayDetectionService()


@router.post("/{session_id}/detect-plays")
async def detect_plays(session_id: str, req: Request) -> dict[str, Any]:
    """Trigger play detection on completed analysis results.

    Runs the play detection engine on the analysis results for the
    given session and stores the detected plays.

    Args:
        session_id: The analysis session UUID.
        req: FastAPI request object for accessing app state.

    Returns:
        Dict with session_id and detected plays.

    Raises:
        HTTPException: If session not found or analysis not complete.
    """
    analysis_service = req.app.state.analysis_service
    provider_factory = req.app.state.provider_factory

    try:
        plays = await _play_detection_service.detect_and_explain(
            session_id=session_id,
            analysis_service=analysis_service,
            provider_factory=provider_factory,
        )
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

    # Store results
    _detected_plays[session_id] = plays

    return {
        "session_id": session_id,
        "plays": plays,
        "count": len(plays),
    }


@router.get("/{session_id}/plays")
async def get_plays(session_id: str, req: Request) -> dict[str, Any]:
    """Retrieve previously detected plays for a session.

    Args:
        session_id: The analysis session UUID.
        req: FastAPI request object for accessing app state.

    Returns:
        Dict with session_id and detected plays.

    Raises:
        HTTPException: If no plays have been detected for this session.
    """
    if session_id not in _detected_plays:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No detected plays found for session '{session_id}'. "
            f"Run POST /api/analysis/{session_id}/detect-plays first.",
        )

    plays = _detected_plays[session_id]
    return {
        "session_id": session_id,
        "plays": plays,
        "count": len(plays),
    }
