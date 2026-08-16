"""Unit tests for the AI Provider Factory."""

import pytest

from src.adapters.ai.claude_provider import ClaudeProvider
from src.adapters.ai.gemini_provider import GeminiProvider
from src.adapters.ai.nvidia_provider import NvidiaProvider
from src.adapters.ai.ollama_provider import OllamaProvider
from src.adapters.ai.openai_provider import OpenAIProvider
from src.adapters.ai.provider_factory import AIProviderFactory
from src.config.settings import Settings
from src.core.enums import AIProvider


@pytest.fixture
def settings():
    """Create test settings with mock API keys."""
    return Settings(
        nvidia_api_key="nvapi-test-key",
        openai_api_key="sk-test-key",
        claude_api_key="sk-ant-test-key",
        gemini_api_key="AIza-test-key",
        default_ai_provider="nvidia",
    )


@pytest.fixture
def settings_no_keys():
    """Create test settings without API keys."""
    return Settings(
        default_ai_provider="nvidia",
    )


@pytest.fixture
def factory(settings):
    """Create a provider factory with test settings."""
    return AIProviderFactory(settings)


@pytest.fixture
def factory_no_keys(settings_no_keys):
    """Create a provider factory without API keys."""
    return AIProviderFactory(settings_no_keys)


class TestFactoryCreation:
    """Tests for factory instantiation."""

    def test_factory_initializes_all_providers(self, factory):
        """Test that factory creates instances for all providers."""
        for provider_enum in AIProvider:
            instance = factory.get_provider(provider_enum)
            assert instance is not None

    def test_factory_creates_correct_types(self, factory):
        """Test that factory creates the correct provider types."""
        assert isinstance(factory.get_provider(AIProvider.NVIDIA), NvidiaProvider)
        assert isinstance(factory.get_provider(AIProvider.OPENAI), OpenAIProvider)
        assert isinstance(factory.get_provider(AIProvider.CLAUDE), ClaudeProvider)
        assert isinstance(factory.get_provider(AIProvider.GEMINI), GeminiProvider)
        assert isinstance(factory.get_provider(AIProvider.OLLAMA), OllamaProvider)

    def test_factory_sets_default_active_provider(self, factory):
        """Test that factory sets the default provider from settings."""
        assert factory.active_provider == AIProvider.NVIDIA

    def test_factory_handles_invalid_default_provider(self):
        """Test that factory falls back to NVIDIA for invalid default."""
        settings = Settings(default_ai_provider="invalid_provider")
        factory = AIProviderFactory(settings)
        assert factory.active_provider == AIProvider.NVIDIA


class TestProviderSwitching:
    """Tests for runtime provider switching."""

    def test_switch_to_configured_provider(self, factory):
        """Test switching to a provider with API key configured."""
        instance = factory.switch_provider(AIProvider.OPENAI)
        assert instance.get_provider_name() == "openai"
        assert factory.active_provider == AIProvider.OPENAI

    def test_switch_to_ollama_always_works(self, factory_no_keys):
        """Test switching to Ollama works even without API keys."""
        instance = factory_no_keys.switch_provider(AIProvider.OLLAMA)
        assert instance.get_provider_name() == "ollama"
        assert factory_no_keys.active_provider == AIProvider.OLLAMA

    def test_switch_to_unconfigured_provider_raises(self, factory_no_keys):
        """Test switching to provider without API key raises ValueError."""
        with pytest.raises(ValueError, match="not configured"):
            factory_no_keys.switch_provider(AIProvider.OPENAI)

    def test_get_active_instance(self, factory):
        """Test getting the active provider instance."""
        instance = factory.active_instance
        assert instance.get_provider_name() == "nvidia"


class TestProviderConfiguration:
    """Tests for runtime configuration updates."""

    def test_update_provider_key(self, factory_no_keys):
        """Test updating API key at runtime."""
        factory_no_keys.update_provider_key(AIProvider.NVIDIA, "nvapi-new-key")
        provider = factory_no_keys.get_provider(AIProvider.NVIDIA)
        assert provider.is_configured() is True

    def test_update_key_enables_provider_switch(self, factory_no_keys):
        """Test that updating key allows switching to that provider."""
        factory_no_keys.update_provider_key(AIProvider.OPENAI, "sk-new-key")
        instance = factory_no_keys.switch_provider(AIProvider.OPENAI)
        assert instance.get_provider_name() == "openai"

    def test_update_invalid_provider_raises(self, factory):
        """Test updating key for invalid provider raises ValueError."""
        with pytest.raises(ValueError):
            factory.update_provider_key("invalid", "key")


class TestListProviders:
    """Tests for listing providers."""

    def test_list_all_providers(self, factory):
        """Test listing all providers."""
        providers = factory.list_providers()
        assert len(providers) == 5
        names = [p["name"] for p in providers]
        assert "nvidia" in names
        assert "openai" in names
        assert "claude" in names
        assert "gemini" in names
        assert "ollama" in names

    def test_list_shows_configured_status(self, factory):
        """Test that list shows correct configuration status."""
        providers = factory.list_providers()
        nvidia = next(p for p in providers if p["name"] == "nvidia")
        assert nvidia["configured"] is True
        assert nvidia["active"] is True

    def test_list_shows_active_provider(self, factory):
        """Test that list correctly marks the active provider."""
        providers = factory.list_providers()
        active_providers = [p for p in providers if p["active"]]
        assert len(active_providers) == 1
        assert active_providers[0]["name"] == "nvidia"

    def test_list_unconfigured_providers(self, factory_no_keys):
        """Test listing unconfigured providers."""
        providers = factory_no_keys.list_providers()
        openai = next(p for p in providers if p["name"] == "openai")
        assert openai["configured"] is False
        # Ollama is always configured
        ollama = next(p for p in providers if p["name"] == "ollama")
        assert ollama["configured"] is True
