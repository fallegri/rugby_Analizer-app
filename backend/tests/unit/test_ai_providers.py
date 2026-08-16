"""Unit tests for AI provider adapters.

Tests that each provider correctly formats API requests and handles responses.
All HTTP calls are mocked.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.adapters.ai.claude_provider import ClaudeProvider
from src.adapters.ai.gemini_provider import GeminiProvider
from src.adapters.ai.nvidia_provider import NvidiaProvider
from src.adapters.ai.ollama_provider import OllamaProvider
from src.adapters.ai.openai_provider import OpenAIProvider


def _mock_response(status_code: int, json_data: dict) -> httpx.Response:
    """Create a mock httpx Response with a request attached."""
    request = httpx.Request("POST", "http://test")
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=request,
    )
    return response


class TestNvidiaProvider:
    """Tests for the NVIDIA AI provider."""

    def test_is_configured_with_key(self):
        """Test provider reports configured when API key is set."""
        provider = NvidiaProvider(api_key="nvapi-test-key")
        assert provider.is_configured() is True

    def test_is_not_configured_without_key(self):
        """Test provider reports not configured without API key."""
        provider = NvidiaProvider(api_key=None)
        assert provider.is_configured() is False

    def test_get_provider_name(self):
        """Test provider name."""
        provider = NvidiaProvider(api_key="test")
        assert provider.get_provider_name() == "nvidia"

    def test_api_key_setter(self):
        """Test updating API key at runtime."""
        provider = NvidiaProvider(api_key=None)
        assert provider.is_configured() is False
        provider.api_key = "nvapi-new-key"
        assert provider.is_configured() is True
        assert provider.api_key == "nvapi-new-key"

    @pytest.mark.asyncio
    async def test_analyze_play_request_format(self):
        """Test that NVIDIA requests match the expected API format."""
        provider = NvidiaProvider(
            api_key="nvapi-test-key",
            model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        )

        mock_resp = _mock_response(200, {
            "choices": [{"message": {"content": "Analysis result"}}]
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.analyze_play("Analyze this play")

            assert result == "Analysis result"
            mock_post.assert_called_once()

            # Verify request format matches NVIDIA API spec
            call_kwargs = mock_post.call_args
            url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url", "")
            assert "integrate.api.nvidia.com/v1/chat/completions" in url

            headers = call_kwargs.kwargs.get("headers", {})
            assert headers["Authorization"] == "Bearer nvapi-test-key"
            assert headers["Accept"] == "application/json"

            payload = call_kwargs.kwargs.get("json", {})
            assert payload["model"] == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
            assert payload["max_tokens"] == 65536
            assert payload["reasoning_budget"] == 16384
            assert payload["stream"] is False
            assert payload["temperature"] == 0.6
            assert payload["top_p"] == 0.95
            assert payload["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_analyze_play_without_key_raises(self):
        """Test that calling without API key raises ValueError."""
        provider = NvidiaProvider(api_key=None)
        with pytest.raises(ValueError, match="API key not configured"):
            await provider.analyze_play("test")

    @pytest.mark.asyncio
    async def test_analyze_positioning(self):
        """Test analyze_positioning returns structured result."""
        provider = NvidiaProvider(api_key="nvapi-test-key")

        mock_resp = _mock_response(200, {
            "choices": [{"message": {"content": "Position analysis"}}]
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.analyze_positioning(
                frame_data={"timestamp": 1.0},
                player_data=[{"id": "p1", "x": 10.0, "y": 20.0}],
            )
            assert result["provider"] == "nvidia"
            assert "analysis" in result

    @pytest.mark.asyncio
    async def test_generate_report(self):
        """Test report generation."""
        provider = NvidiaProvider(api_key="nvapi-test-key")

        mock_resp = _mock_response(200, {
            "choices": [{"message": {"content": "Match report"}}]
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.generate_report({"total_distance": 5.2})
            assert result == "Match report"


class TestOpenAIProvider:
    """Tests for the OpenAI AI provider."""

    def test_is_configured(self):
        """Test configuration status."""
        provider = OpenAIProvider(api_key="sk-test")
        assert provider.is_configured() is True
        assert provider.get_provider_name() == "openai"

    def test_is_not_configured(self):
        """Test not configured without key."""
        provider = OpenAIProvider(api_key=None)
        assert provider.is_configured() is False

    @pytest.mark.asyncio
    async def test_analyze_play_request_format(self):
        """Test OpenAI request format."""
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")

        mock_resp = _mock_response(200, {
            "choices": [{"message": {"content": "OpenAI analysis"}}]
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.analyze_play("Test prompt")

            assert result == "OpenAI analysis"
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json", {})
            assert payload["model"] == "gpt-4"
            assert any(m["role"] == "system" for m in payload["messages"])
            assert any(m["role"] == "user" for m in payload["messages"])


class TestClaudeProvider:
    """Tests for the Claude AI provider."""

    def test_is_configured(self):
        """Test configuration status."""
        provider = ClaudeProvider(api_key="sk-ant-test")
        assert provider.is_configured() is True
        assert provider.get_provider_name() == "claude"

    @pytest.mark.asyncio
    async def test_analyze_play_request_format(self):
        """Test Claude (Anthropic) request format."""
        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-3-5-sonnet-20241022")

        mock_resp = _mock_response(200, {"content": [{"text": "Claude analysis"}]})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.analyze_play("Test prompt")

            assert result == "Claude analysis"
            call_kwargs = mock_post.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "x-api-key" in headers
            assert "anthropic-version" in headers
            payload = call_kwargs.kwargs.get("json", {})
            assert payload["model"] == "claude-3-5-sonnet-20241022"


class TestGeminiProvider:
    """Tests for the Gemini AI provider."""

    def test_is_configured(self):
        """Test configuration status."""
        provider = GeminiProvider(api_key="AIza-test")
        assert provider.is_configured() is True
        assert provider.get_provider_name() == "gemini"

    @pytest.mark.asyncio
    async def test_analyze_play_request_format(self):
        """Test Gemini request format."""
        provider = GeminiProvider(api_key="AIza-test", model="gemini-pro")

        mock_resp = _mock_response(200, {
            "candidates": [{"content": {"parts": [{"text": "Gemini analysis"}]}}]
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.analyze_play("Test prompt")

            assert result == "Gemini analysis"
            call_kwargs = mock_post.call_args
            url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url", "")
            assert "gemini-pro:generateContent" in url
            assert "key=AIza-test" in url


class TestOllamaProvider:
    """Tests for the Ollama AI provider."""

    def test_is_always_configured(self):
        """Test Ollama is always considered configured (no API key needed)."""
        provider = OllamaProvider()
        assert provider.is_configured() is True
        assert provider.get_provider_name() == "ollama"

    @pytest.mark.asyncio
    async def test_analyze_play_request_format(self):
        """Test Ollama request format."""
        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3")

        mock_resp = _mock_response(200, {"response": "Ollama analysis"})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            result = await provider.analyze_play("Test prompt")

            assert result == "Ollama analysis"
            call_kwargs = mock_post.call_args
            url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url", "")
            assert "localhost:11434/api/generate" in url
            payload = call_kwargs.kwargs.get("json", {})
            assert payload["model"] == "llama3"
            assert payload["stream"] is False

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test graceful handling when Ollama is not running."""
        provider = OllamaProvider(base_url="http://localhost:11434")

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(ConnectionError, match="Cannot connect to Ollama"):
                await provider.analyze_play("test")
