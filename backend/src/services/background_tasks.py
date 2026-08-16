"""Background task management for video processing.

Uses asyncio.create_task for local deployment (no Celery required).
Tracks active tasks and supports cancellation.
Sends rich progress updates with stages, timing, and FPS info.
"""

import asyncio
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Processing stage definitions (Spanish labels for user display)
STAGE_LOADING = "Cargando video"
STAGE_DETECTING = "Detectando jugadores"
STAGE_TRACKING = "Tracking"
STAGE_CALIBRATING = "Calibrando cancha"
STAGE_ANALYTICS = "Calculando analiticas"
STAGE_COMPLETE = "Completado"


class BackgroundTaskManager:
    """Manages background video processing tasks using asyncio.

    Tracks active tasks, provides cancellation, and coordinates
    progress updates through the AnalysisService and WebSocket manager.
    """

    def __init__(self):
        """Initialize the task manager."""
        self._active_tasks: dict[str, asyncio.Task] = {}

    async def start_processing(
        self,
        session_id: str,
        video_path: str,
        mode: str,
        target_ids: list[int],
        analysis_service: Any,
        ws_manager: Optional[Any] = None,
        video_processor: Optional[Any] = None,
    ) -> None:
        """Start a background video processing task.

        Args:
            session_id: The analysis session ID.
            video_path: Path to the video file.
            mode: Tracking mode string.
            target_ids: List of target track IDs.
            analysis_service: Service for updating session state.
            ws_manager: WebSocket manager for progress broadcasts.
            video_processor: VideoProcessor instance (injected for testability).
        """
        task = asyncio.create_task(
            self._process_video_task(
                session_id=session_id,
                video_path=video_path,
                mode=mode,
                target_ids=target_ids,
                analysis_service=analysis_service,
                ws_manager=ws_manager,
                video_processor=video_processor,
            )
        )
        self._active_tasks[session_id] = task
        logger.info(f"Started background task for session: {session_id}")

    async def _process_video_task(
        self,
        session_id: str,
        video_path: str,
        mode: str,
        target_ids: list[int],
        analysis_service: Any,
        ws_manager: Optional[Any] = None,
        video_processor: Optional[Any] = None,
    ) -> None:
        """Execute the video processing pipeline as a background task.

        Sends rich progress messages including stage name, frame info,
        elapsed time, ETA, FPS, and a heartbeat timestamp for stall detection.

        Args:
            session_id: The analysis session ID.
            video_path: Path to the video file.
            mode: Tracking mode.
            target_ids: Target IDs for tracking.
            analysis_service: Service for updating progress/results.
            ws_manager: WebSocket connection manager for broadcasting.
            video_processor: VideoProcessor instance.
        """
        try:
            if video_processor is None:
                analysis_service.mark_failed(session_id, "No video processor available")
                return

            # Track timing for progress reporting
            start_time = time.time()
            last_broadcast_time = start_time
            last_broadcast_frame = 0
            current_stage = STAGE_LOADING
            broadcast_interval = 0.5  # Send updates every 500ms max

            # Notify loading stage
            if ws_manager:
                await ws_manager.broadcast_progress(
                    session_id=session_id,
                    progress=0.0,
                    status="processing",
                    data={
                        "stage": current_stage,
                        "current_frame": 0,
                        "total_frames": 0,
                        "fps": 0.0,
                        "elapsed_time": 0.0,
                        "eta": 0.0,
                    },
                )

            # Define progress callback with rich data
            def progress_callback(current_frame: int, total_frames: int) -> None:
                nonlocal last_broadcast_time, last_broadcast_frame, current_stage

                analysis_service.update_progress(session_id, current_frame, total_frames)

                now = time.time()
                elapsed = now - start_time

                # Throttle WebSocket broadcasts
                if now - last_broadcast_time < broadcast_interval:
                    return

                # Determine current stage based on progress
                progress_pct = (current_frame / total_frames * 100.0) if total_frames > 0 else 0.0
                if progress_pct < 5:
                    current_stage = STAGE_LOADING
                elif progress_pct < 40:
                    current_stage = STAGE_DETECTING
                elif progress_pct < 70:
                    current_stage = STAGE_TRACKING
                elif progress_pct < 90:
                    current_stage = STAGE_CALIBRATING
                else:
                    current_stage = STAGE_ANALYTICS

                # Calculate processing FPS
                frames_since_last = current_frame - last_broadcast_frame
                time_since_last = now - last_broadcast_time
                processing_fps = frames_since_last / time_since_last if time_since_last > 0 else 0.0

                # Calculate ETA
                if current_frame > 0 and total_frames > 0:
                    avg_time_per_frame = elapsed / current_frame
                    remaining_frames = total_frames - current_frame
                    eta = avg_time_per_frame * remaining_frames
                else:
                    eta = 0.0

                last_broadcast_time = now
                last_broadcast_frame = current_frame

                # Queue the WebSocket broadcast (non-blocking from sync context)
                if ws_manager:
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                ws_manager.broadcast_progress(
                                    session_id=session_id,
                                    progress=round(progress_pct, 1),
                                    status="processing",
                                    data={
                                        "stage": current_stage,
                                        "current_frame": current_frame,
                                        "total_frames": total_frames,
                                        "fps": round(processing_fps, 1),
                                        "elapsed_time": round(elapsed, 1),
                                        "eta": round(eta, 1),
                                    },
                                ),
                                loop,
                            )
                    except RuntimeError:
                        pass  # Event loop not available (e.g. during tests)

            # Run the synchronous video processing in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: video_processor.process_video(
                    video_path=video_path,
                    target_ids=target_ids if target_ids else None,
                    progress_callback=progress_callback,
                ),
            )

            # Convert result to serializable dict
            results_dict = {
                "total_frames": result.total_frames,
                "fps": result.fps,
                "duration_s": result.duration_s,
                "analytics": {
                    str(track_id): {
                        "max_speed": getattr(analytics, "max_speed", None),
                        "avg_speed": getattr(analytics, "avg_speed", None),
                        "total_distance": getattr(analytics, "total_distance", None),
                    }
                    for track_id, analytics in result.analytics.items()
                },
            }

            analysis_service.mark_completed(session_id, results_dict)

            # Send completion notification via WebSocket
            if ws_manager:
                total_elapsed = time.time() - start_time
                await ws_manager.broadcast_progress(
                    session_id=session_id,
                    progress=100.0,
                    status="completed",
                    data={
                        "stage": STAGE_COMPLETE,
                        "current_frame": result.total_frames,
                        "total_frames": result.total_frames,
                        "fps": 0.0,
                        "elapsed_time": round(total_elapsed, 1),
                        "eta": 0.0,
                        "results": results_dict,
                    },
                )

            logger.info(f"Completed processing for session: {session_id}")

        except asyncio.CancelledError:
            analysis_service.mark_failed(session_id, "Task cancelled")
            logger.info(f"Task cancelled for session: {session_id}")
            raise
        except Exception as e:
            error_msg = str(e)
            analysis_service.mark_failed(session_id, error_msg)
            logger.error(f"Processing failed for session {session_id}: {error_msg}")

            if ws_manager:
                await ws_manager.send_message(
                    session_id,
                    {"type": "error", "session_id": session_id, "error": error_msg},
                )
        finally:
            self._active_tasks.pop(session_id, None)

    async def cancel_task(self, session_id: str) -> bool:
        """Cancel an active processing task.

        Args:
            session_id: The session whose task should be cancelled.

        Returns:
            True if a task was found and cancelled, False otherwise.
        """
        task = self._active_tasks.get(session_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled task for session: {session_id}")
            return True
        return False

    def is_active(self, session_id: str) -> bool:
        """Check if a task is currently active for the given session."""
        task = self._active_tasks.get(session_id)
        return task is not None and not task.done()

    def get_active_sessions(self) -> list[str]:
        """Get list of sessions with active processing tasks."""
        return [
            sid for sid, task in self._active_tasks.items() if not task.done()
        ]
