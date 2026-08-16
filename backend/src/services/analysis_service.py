"""Analysis orchestration service.

Ties together video processing, tracking, calibration, and AI analysis.
Manages analysis sessions and delegates work to background tasks.
"""

import logging
from typing import Any, Optional
from uuid import uuid4

from src.core.enums import AnalysisStatus, TrackingMode
from src.core.models import AnalysisRequest

logger = logging.getLogger(__name__)


class AnalysisService:
    """Orchestrates the full analysis pipeline.

    Manages session lifecycle: creation, status tracking, and result retrieval.
    Delegates actual processing to the BackgroundTaskManager.
    """

    def __init__(self):
        """Initialize analysis service with in-memory session storage.

        TODO: MVP limitation - sessions are stored in-memory and lost on restart.
        For production, persist sessions to SQLite/Postgres via the repository pattern.
        Multi-worker deployments will also require shared state (Redis or database).
        """
        self._sessions: dict[str, dict[str, Any]] = {}

    def start_analysis(self, request: AnalysisRequest) -> str:
        """Start a new analysis session.

        Validates the request, creates a session record, and returns
        the session ID. Background processing is started separately.

        Args:
            request: The analysis request with video, mode, and calibration info.

        Returns:
            The session ID string.

        Raises:
            ValueError: If the request is invalid.
        """
        session_id = str(uuid4())

        self._sessions[session_id] = {
            "session_id": session_id,
            "video_id": str(request.video_id),
            "mode": request.mode.value,
            "status": AnalysisStatus.PENDING.value,
            "progress": 0.0,
            "current_frame": 0,
            "total_frames": 0,
            "results": None,
            "error": None,
        }

        logger.info(f"Created analysis session {session_id} for video {request.video_id}")
        return session_id

    def get_status(self, session_id: str) -> dict[str, Any]:
        """Get current status and progress of an analysis session.

        Args:
            session_id: The session to check.

        Returns:
            Dict with status, progress percentage, current_frame, total_frames.

        Raises:
            KeyError: If session_id is not found.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' not found")

        session = self._sessions[session_id]
        return {
            "session_id": session_id,
            "status": session["status"],
            "progress": session["progress"],
            "current_frame": session["current_frame"],
            "total_frames": session["total_frames"],
        }

    def get_results(self, session_id: str) -> dict[str, Any]:
        """Get completed analysis results.

        Args:
            session_id: The session to retrieve results for.

        Returns:
            Dict with full analysis results.

        Raises:
            KeyError: If session_id is not found.
            ValueError: If analysis is not yet complete.
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' not found")

        session = self._sessions[session_id]

        if session["status"] != AnalysisStatus.COMPLETED.value:
            raise ValueError(
                f"Analysis not complete. Current status: {session['status']}"
            )

        return {
            "session_id": session_id,
            "video_id": session["video_id"],
            "mode": session["mode"],
            "status": session["status"],
            "results": session["results"],
        }

    def update_progress(
        self, session_id: str, current_frame: int, total_frames: int
    ) -> None:
        """Update the progress of an analysis session.

        Args:
            session_id: The session to update.
            current_frame: Current frame being processed.
            total_frames: Total frames in the video.
        """
        if session_id not in self._sessions:
            return

        progress = (current_frame / total_frames * 100.0) if total_frames > 0 else 0.0
        self._sessions[session_id]["progress"] = round(progress, 1)
        self._sessions[session_id]["current_frame"] = current_frame
        self._sessions[session_id]["total_frames"] = total_frames
        self._sessions[session_id]["status"] = AnalysisStatus.PROCESSING.value

    def mark_completed(self, session_id: str, results: dict[str, Any]) -> None:
        """Mark a session as completed with results.

        Args:
            session_id: The session to mark.
            results: The analysis results.
        """
        if session_id not in self._sessions:
            return

        self._sessions[session_id]["status"] = AnalysisStatus.COMPLETED.value
        self._sessions[session_id]["progress"] = 100.0
        self._sessions[session_id]["results"] = results

    def mark_failed(self, session_id: str, error: str) -> None:
        """Mark a session as failed with error details.

        Args:
            session_id: The session to mark.
            error: Error description.
        """
        if session_id not in self._sessions:
            return

        self._sessions[session_id]["status"] = AnalysisStatus.FAILED.value
        self._sessions[session_id]["error"] = error

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self._sessions
