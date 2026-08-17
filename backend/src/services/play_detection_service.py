"""Play detection service.

Orchestrates play detection from analysis results and enriches
detected plays with AI-generated explanations.
"""

import logging
from dataclasses import asdict
from typing import Any

from src.cv.play_detector import DetectedPlay, PlayDetector

logger = logging.getLogger(__name__)


class PlayDetectionService:
    """Service that detects rugby plays and enriches them with AI explanations.

    Coordinates between the PlayDetector (algorithmic detection) and the
    AI provider (tactical explanation/confirmation).
    """

    def __init__(self):
        self._detector = PlayDetector()

    async def detect_and_explain(
        self,
        session_id: str,
        analysis_service: Any,
        provider_factory: Any,
    ) -> list[dict[str, Any]]:
        """Detect plays from analysis results and get AI explanations.

        Args:
            session_id: The analysis session ID.
            analysis_service: The AnalysisService instance to get results from.
            provider_factory: The AIProviderFactory for AI explanations.

        Returns:
            List of detected plays as serializable dicts.

        Raises:
            KeyError: If session_id is not found.
            ValueError: If analysis is not yet complete.
        """
        # Get analysis results
        results = analysis_service.get_results(session_id)
        analysis_data = results.get("results", {})

        # Extract players data - the results dict has a 'players' key
        # which is a list of player dicts with route, speeds, etc.
        players_data = analysis_data.get("players", [])

        if not players_data:
            return []

        # Run play detection
        detected_plays = self._detector.detect_plays(players_data)

        if not detected_plays:
            return []

        # Enrich with AI explanations
        enriched_plays = await self._enrich_with_ai(
            detected_plays, provider_factory
        )

        return [self._play_to_dict(play) for play in enriched_plays]

    async def _enrich_with_ai(
        self,
        plays: list[DetectedPlay],
        provider_factory: Any,
    ) -> list[DetectedPlay]:
        """Enrich detected plays with AI explanations.

        If the AI provider is not configured or fails, the plays are
        returned without explanations (ai_explanation remains None).
        """
        try:
            provider = provider_factory.get_provider()
            if not provider.is_configured():
                logger.info("AI provider not configured, skipping explanations")
                return plays
        except Exception as e:
            logger.warning(f"Could not get AI provider: {e}")
            return plays

        enriched: list[DetectedPlay] = []
        for play in plays:
            try:
                prompt = self._build_explanation_prompt(play)
                context = self._build_explanation_context(play)
                explanation = await provider.analyze_play(prompt, context)
                play.ai_explanation = explanation
            except Exception as e:
                logger.warning(
                    f"AI explanation failed for {play.play_type} at "
                    f"t={play.start_time:.1f}s: {e}"
                )
                # Leave ai_explanation as None
            enriched.append(play)

        return enriched

    def _build_explanation_prompt(self, play: DetectedPlay) -> str:
        """Build an AI prompt for explaining a detected play."""
        return (
            f"A rugby {play.play_type} was detected at position "
            f"({play.position[0]:.1f}, {play.position[1]:.1f}) on the field "
            f"from {play.start_time:.1f}s to {play.end_time:.1f}s. "
            f"Players involved: {', '.join(play.players_involved)}. "
            f"Detection details: {play.description}. "
            f"Please confirm if this is likely a valid {play.play_type} "
            f"and provide a brief tactical explanation of what may be happening."
        )

    def _build_explanation_context(self, play: DetectedPlay) -> str:
        """Build context string for the AI provider."""
        return (
            f"Play type: {play.play_type}\n"
            f"Time: {play.start_time:.1f}s - {play.end_time:.1f}s\n"
            f"Position: ({play.position[0]:.1f}, {play.position[1]:.1f})\n"
            f"Confidence: {play.confidence:.2f}\n"
            f"Players: {', '.join(play.players_involved)}\n"
            f"Description: {play.description}"
        )

    def _play_to_dict(self, play: DetectedPlay) -> dict[str, Any]:
        """Convert a DetectedPlay to a serializable dict."""
        return {
            "play_type": play.play_type,
            "start_time": play.start_time,
            "end_time": play.end_time,
            "confidence": play.confidence,
            "players_involved": play.players_involved,
            "position": list(play.position),
            "description": play.description,
            "ai_explanation": play.ai_explanation,
        }
