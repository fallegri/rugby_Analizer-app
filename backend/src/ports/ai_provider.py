"""AI Provider port - abstract interface for AI provider adapters.

This module defines the contract that all AI provider adapters must fulfill.
Follows the hexagonal architecture (ports & adapters) pattern.
"""

from abc import ABC, abstractmethod
from typing import Any


class AIProviderPort(ABC):
    """Abstract base class defining the AI provider interface.

    All concrete AI provider adapters must implement these methods
    to ensure interchangeability via the Strategy pattern.
    """

    @abstractmethod
    async def analyze_play(self, prompt: str, context: str = "") -> str:
        """Analyze a play based on provided prompt and context.

        Args:
            prompt: The analysis question or instruction.
            context: Additional context about the play (positions, movements, etc.)

        Returns:
            AI-generated analysis text.
        """
        ...

    @abstractmethod
    async def analyze_positioning(
        self, frame_data: dict[str, Any], player_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze player positioning from frame and player data.

        Args:
            frame_data: Data about the current frame (timestamp, field zones, etc.)
            player_data: List of player position/movement data.

        Returns:
            Dictionary with positioning analysis results.
        """
        ...

    @abstractmethod
    async def generate_report(self, analysis_data: dict[str, Any]) -> str:
        """Generate a comprehensive analysis report.

        Args:
            analysis_data: Aggregated analysis data from tracking session.

        Returns:
            Formatted report text.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider name identifier."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Check whether the provider has valid configuration (API key, etc.)."""
        ...
