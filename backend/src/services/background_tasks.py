"""Background task management for video processing.

Uses asyncio.create_task for local deployment (no Celery required).
Tracks active tasks and supports cancellation.
Sends rich progress updates with stages, timing, and FPS info.
"""

import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
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
        video_metadata: Optional[dict] = None,
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
            video_metadata: Video metadata dict (filename, description) for result persistence.
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
                video_metadata=video_metadata,
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
        video_metadata: Optional[dict] = None,
    ) -> None:
        """Execute the video processing pipeline as a background task.

        Sends rich progress messages including stage name, frame info,
        elapsed time, ETA, FPS, and a heartbeat timestamp for stall detection.
        After completion, deletes the video file and persists results to disk.

        Args:
            session_id: The analysis session ID.
            video_path: Path to the video file.
            mode: Tracking mode.
            target_ids: Target IDs for tracking.
            analysis_service: Service for updating progress/results.
            ws_manager: WebSocket connection manager for broadcasting.
            video_processor: VideoProcessor instance.
            video_metadata: Video metadata dict (filename, description).
        """
        try:
            if video_processor is None:
                error_msg = "No video processor available - CV pipeline not initialized"
                logger.error(f"[Session {session_id}] FAILED: {error_msg}")
                analysis_service.mark_failed(session_id, error_msg)
                if ws_manager:
                    await ws_manager.send_message(
                        session_id,
                        {
                            "type": "error",
                            "session_id": session_id,
                            "error": error_msg,
                        },
                    )
                return

            # Track timing for progress reporting
            start_time = time.time()
            last_broadcast_time = start_time
            last_broadcast_frame = 0
            current_stage = STAGE_LOADING
            broadcast_interval = 0.5  # Send updates every 500ms max

            logger.info(
                f"[Session {session_id}] Stage: {STAGE_LOADING} | "
                f"Video: {video_path} | Mode: {mode}"
            )

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
                prev_stage = current_stage
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

                # Log stage transitions
                if prev_stage != current_stage:
                    logger.info(
                        f"[Session {session_id}] Stage: {current_stage} | "
                        f"Frame {current_frame}/{total_frames} | "
                        f"{progress_pct:.1f}% | FPS: {processing_fps:.1f}"
                    )

                # Log progress every broadcast interval
                logger.debug(
                    f"[Session {session_id}] Progress: {current_frame}/{total_frames} "
                    f"({progress_pct:.1f}%) | Stage: {current_stage} | "
                    f"FPS: {processing_fps:.1f} | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s"
                )

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
            logger.info(
                f"[Session {session_id}] Starting video processing in thread pool | "
                f"Video: {video_path} | Mode: {mode} | Targets: {target_ids}"
            )
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: video_processor.process_video(
                    video_path=video_path,
                    target_ids=target_ids if target_ids else None,
                    progress_callback=progress_callback,
                ),
            )

            # Convert result to serializable dict matching frontend PlayerMetrics[] format
            players_list = []
            for track_id, analytics in result.analytics.items():
                # Build keypoints lookup for this track (frame_num -> keypoints)
                track_kps = result.track_keypoints.get(track_id, {}) if hasattr(result, "track_keypoints") else {}

                player_metrics = {
                    "player_id": str(track_id),
                    "total_distance_km": getattr(analytics, "total_distance_km", 0.0),
                    "max_speed_kmh": getattr(analytics, "max_speed_kmh", 0.0),
                    "avg_speed_kmh": getattr(analytics, "avg_speed_kmh", 0.0),
                    "sprint_count": len(getattr(analytics, "sprint_segments", [])),
                    "team_id": result.team_classifications.get(track_id) if hasattr(result, "team_classifications") else None,
                    "sprints": [
                        {
                            "start_time": seg.start_frame / result.fps if result.fps > 0 else 0.0,
                            "end_time": seg.end_frame / result.fps if result.fps > 0 else 0.0,
                            "max_speed": seg.max_speed_kmh,
                            "distance": seg.distance_m,
                        }
                        for seg in getattr(analytics, "sprint_segments", [])
                    ],
                    "route": [],
                }

                # Build route points with keypoints. Route points use timestamp_s
                # which maps back to frame_num via fps.
                route_points = getattr(analytics, "route_points", [])
                for pt in route_points:
                    route_entry: dict = {
                        "x": pt[0],
                        "y": pt[1],
                        "timestamp": pt[2],
                        "speed": 0.0,
                    }
                    # Map timestamp back to frame number to find keypoints
                    if track_kps and result.fps > 0:
                        frame_num_approx = int(round(pt[2] * result.fps))
                        kps = track_kps.get(frame_num_approx)
                        if kps:
                            route_entry["keypoints"] = [
                                {"x": kp[0], "y": kp[1], "confidence": kp[2]}
                                for kp in kps
                            ]
                    player_metrics["route"].append(route_entry)
                # Compute speed for each route point (distance / time between consecutive points)
                route = player_metrics["route"]
                for i in range(1, len(route)):
                    prev = route[i - 1]
                    curr = route[i]
                    dt = curr["timestamp"] - prev["timestamp"]
                    if dt > 0:
                        dist = math.sqrt((curr["x"] - prev["x"]) ** 2 + (curr["y"] - prev["y"]) ** 2)
                        speed_ms = dist / dt
                        curr["speed"] = speed_ms  # m/s for frontend chart (converts to km/h via *3.6)
                    else:
                        curr["speed"] = 0.0

                players_list.append(player_metrics)

            results_dict = {
                "total_frames": result.total_frames,
                "fps": result.fps,
                "duration_s": result.duration_s,
                "players": players_list,
            }

            analysis_service.mark_completed(session_id, results_dict)

            # Auto-cleanup: persist results to disk and delete video file
            self._persist_results(
                session_id=session_id,
                mode=mode,
                results_dict=results_dict,
                video_metadata=video_metadata,
            )
            self._cleanup_video_file(video_path, session_id)

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

            total_elapsed = time.time() - start_time
            logger.info(
                f"[Session {session_id}] Stage: {STAGE_COMPLETE} | "
                f"Frames: {result.total_frames} | Duration: {result.duration_s:.1f}s | "
                f"Processing time: {total_elapsed:.1f}s | "
                f"Avg FPS: {result.total_frames / total_elapsed:.1f}" if total_elapsed > 0 else
                f"[Session {session_id}] Stage: {STAGE_COMPLETE} | Frames: {result.total_frames}"
            )

        except asyncio.CancelledError:
            analysis_service.mark_failed(session_id, "Task cancelled")
            logger.warning(f"[Session {session_id}] CANCELLED by user request")
            if ws_manager:
                await ws_manager.send_message(
                    session_id,
                    {
                        "type": "error",
                        "session_id": session_id,
                        "error": "Processing was cancelled",
                    },
                )
            raise
        except Exception as e:
            error_msg = str(e)
            analysis_service.mark_failed(session_id, error_msg)
            logger.error(
                f"[Session {session_id}] FAILED: {error_msg}",
                exc_info=True,
            )

            if ws_manager:
                await ws_manager.send_message(
                    session_id,
                    {"type": "error", "session_id": session_id, "error": error_msg},
                )
        finally:
            self._active_tasks.pop(session_id, None)

    def _cleanup_video_file(self, video_path: str, session_id: str) -> None:
        """Delete the video file from disk after processing completes.

        Args:
            video_path: Path to the video file to delete.
            session_id: Session ID for logging.
        """
        try:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
                logger.info(
                    f"[Session {session_id}] Auto-cleanup: deleted video file {video_path}"
                )
            else:
                logger.debug(
                    f"[Session {session_id}] Auto-cleanup: video file not found at {video_path}"
                )
        except OSError as e:
            logger.warning(
                f"[Session {session_id}] Auto-cleanup: failed to delete video file "
                f"{video_path}: {e}"
            )

    def _persist_results(
        self,
        session_id: str,
        mode: str,
        results_dict: dict[str, Any],
        video_metadata: Optional[dict] = None,
    ) -> None:
        """Persist analysis results to a JSON file in the results/ directory.

        Saves video metadata (name, description, processing timestamp, session_id)
        along with the full analysis results.

        Args:
            session_id: The analysis session ID.
            mode: Tracking mode used.
            results_dict: The analysis results dictionary.
            video_metadata: Video metadata dict with filename and description.
        """
        try:
            results_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "results",
            )
            os.makedirs(results_dir, exist_ok=True)

            video_name = ""
            video_description = None
            if video_metadata:
                video_name = video_metadata.get("filename", "")
                video_description = video_metadata.get("description")

            analysis_record = {
                "video_name": video_name,
                "video_description": video_description,
                "analysis_date": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "mode": mode,
                "players": results_dict.get("players", []),
                "detected_plays": results_dict.get("detected_plays", []),
                "total_frames": results_dict.get("total_frames"),
                "fps": results_dict.get("fps"),
                "duration_s": results_dict.get("duration_s"),
            }

            result_file = os.path.join(results_dir, f"{session_id}.json")
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(analysis_record, f, indent=2, ensure_ascii=False)

            logger.info(
                f"[Session {session_id}] Persisted results to {result_file}"
            )
        except Exception as e:
            logger.warning(
                f"[Session {session_id}] Failed to persist results: {e}"
            )

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
