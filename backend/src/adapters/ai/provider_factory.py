"""AI Provider Factory - creates provider instances based on configuration.

Implements the Factory pattern for AI provider instantiation.
Supports runtime switching between providers.
"""

import logging
from typing import Optional

from src.adapters.ai.claude_provider import ClaudeProvider
from src.adapters.ai.gemini_provider import GeminiProvider
from src.adapters.ai.nvidia_provider import NvidiaProvider
from src.adapters.ai.ollama_provider import OllamaProvider
from src.adapters.ai.openai_provider import OpenAIProvider
from src.config.settings import Settings
from src.core.enums import AIProvider
from src.ports.ai_provider import AIProviderPort

logger = logging.getLogger(__name__)


class AIProviderFactory:
    """Factory for creating and managing AI provider instances.

    Supports runtime switching between providers and validates
    that the selected provider has valid configuration.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._providers: dict[AIProvider, AIProviderPort] = {}
        self._active_provider: Optional[AIProvider] = None
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize all provider instances with current settings."""
        self._providers[AIProvider.NVIDIA] = NvidiaProvider(
            api_key=self._settings.nvidia_api_key,
            model=self._settings.nvidia_model,
            base_url=self._settings.nvidia_base_url,
        )
        self._providers[AIProvider.OPENAI] = OpenAIProvider(
            api_key=self._settings.openai_api_key,
            model=self._settings.openai_model,
            base_url=self._settings.openai_base_url,
        )
        self._providers[AIProvider.CLAUDE] = ClaudeProvider(
            api_key=self._settings.claude_api_key,
            model=self._settings.claude_model,
            base_url=self._settings.claude_base_url,
        )
        self._providers[AIProvider.GEMINI] = GeminiProvider(
            api_key=self._settings.gemini_api_key,
            model=self._settings.gemini_model,
            base_url=self._settings.gemini_base_url,
        )
        self._providers[AIProvider.OLLAMA] = OllamaProvider(
            base_url=self._settings.ollama_base_url,
            model=self._settings.ollama_model,
        )

        # Set the default active provider
        try:
            self._active_provider = AIProvider(self._settings.default_ai_provider)
        except ValueError:
            logger.warning(
                f"Invalid default provider '{self._settings.default_ai_provider}', "
                f"falling back to NVIDIA"
            )
            self._active_provider = AIProvider.NVIDIA

    def get_provider(self, provider: Optional[AIProvider] = None) -> AIProviderPort:
        """Get a specific provider instance or the active provider.

        Args:
            provider: Specific provider to get. If None, returns active provider.

        Returns:
            The requested AI provider instance.

        Raises:
            ValueError: If the provider is not found or not configured.
        """
        target = provider or self._active_provider
        if target not in self._providers:
            raise ValueError(f"Unknown AI provider: {target}")
        return self._providers[target]

    def switch_provider(self, provider: AIProvider) -> AIProviderPort:
        """Switch the active AI provider.

        Args:
            provider: The provider to switch to.

        Returns:
            The newly active provider instance.

        Raises:
            ValueError: If the provider is not available or not configured.
        """
        if provider not in self._providers:
            raise ValueError(f"Unknown AI provider: {provider}")

        instance = self._providers[provider]
        if not instance.is_configured():
            raise ValueError(
                f"Provider '{provider.value}' is not configured. "
                f"Please set the API key first."
            )

        self._active_provider = provider
        logger.info(f"Switched active AI provider to: {provider.value}")
        return instance

    def update_provider_key(self, provider: AIProvider, api_key: str) -> None:
        """Update the API key for a specific provider at runtime.

        Args:
            provider: The provider to update.
            api_key: The new API key.
        """
        if provider not in self._providers:
            raise ValueError(f"Unknown AI provider: {provider}")

        instance = self._providers[provider]
        instance.api_key = api_key
        logger.info(f"Updated API key for provider: {provider.value}")

    def list_providers(self) -> list[dict]:
        """List all available providers with their configuration status.

        Returns:
            List of provider info dictionaries.
        """
        result = []
        for provider_enum, instance in self._providers.items():
            result.append(
                {
                    "name": provider_enum.value,
                    "configured": instance.is_configured(),
                    "active": provider_enum == self._active_provider,
                }
            )
        return result

    @property
    def active_provider(self) -> Optional[AIProvider]:
        """Get the currently active provider enum value."""
        return self._active_provider

    @property
    def active_instance(self) -> AIProviderPort:
        """Get the currently active provider instance."""
        return self.get_provider()
