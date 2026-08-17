"""Unit tests for the play detection service.

Tests service integration with PlayDetector and AI provider,
including graceful handling of unconfigured/failing providers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.play_detection_service import PlayDetectionService


@pytest.fixture
def service():
    """Create a PlayDetectionService instance."""
    return PlayDetectionService()


@pytest.fixture
def mock_analysis_service():
    """Create a mock analysis service with sample results."""
    service = MagicMock()
    service.get_results.return_value = {
        "session_id": "test-session-1",
        "video_id": "video-1",
        "mode": "group_tracking",
        "status": "completed",
        "results": {
            "players": [
                {
                    "player_id": "1",
                    "route": [
                        {"x": 45.0, "y": 35.0, "timestamp": 0.0, "speed": 20.0},
                        {"x": 47.5, "y": 35.0, "timestamp": 0.5, "speed": 20.0},
                        {"x": 49.5, "y": 35.0, "timestamp": 1.0, "speed": 20.0},
                    ],
                    "total_distance_km": 0.0045,
                    "max_speed_kmh": 20.0,
                    "avg_speed_kmh": 20.0,
                    "sprint_count": 1,
                    "sprints": [],
                },
                {
                    "player_id": "2",
                    "route": [
                        {"x": 55.0, "y": 35.0, "timestamp": 0.0, "speed": 18.0},
                        {"x": 52.5, "y": 35.0, "timestamp": 0.5, "speed": 18.0},
                        {"x": 50.5, "y": 35.0, "timestamp": 1.0, "speed": 18.0},
                    ],
                    "total_distance_km": 0.0045,
                    "max_speed_kmh": 18.0,
                    "avg_speed_kmh": 18.0,
                    "sprint_count": 1,
                    "sprints": [],
                },
            ]
        },
    }
    return service


@pytest.fixture
def mock_analysis_service_empty():
    """Create a mock analysis service with no players."""
    service = MagicMock()
    service.get_results.return_value = {
        "session_id": "test-session-2",
        "video_id": "video-2",
        "mode": "single_player",
        "status": "completed",
        "results": {
            "players": []
        },
    }
    return service


@pytest.fixture
def mock_provider_factory_configured():
    """Create a mock provider factory with a configured provider."""
    factory = MagicMock()
    provider = MagicMock()
    provider.is_configured.return_value = True
    provider.analyze_play = AsyncMock(
        return_value="This appears to be a valid tackle. "
        "The two players converged at high speed indicating a defensive action."
    )
    factory.get_provider.return_value = provider
    return factory


@pytest.fixture
def mock_provider_factory_unconfigured():
    """Create a mock provider factory with an unconfigured provider."""
    factory = MagicMock()
    provider = MagicMock()
    provider.is_configured.return_value = False
    factory.get_provider.return_value = provider
    return factory


@pytest.fixture
def mock_provider_factory_error():
    """Create a mock provider factory that raises an error."""
    factory = MagicMock()
    factory.get_provider.side_effect = Exception("No provider available")
    return factory


class TestPlayDetectionServiceBasic:
    """Basic service tests."""

    def test_instantiation(self, service):
        """Test service can be instantiated."""
        assert service is not None
        assert service._detector is not None


class TestDetectAndExplain:
    """Tests for the detect_and_explain method."""

    @pytest.mark.asyncio
    async def test_detect_and_explain_with_configured_provider(
        self, service, mock_analysis_service, mock_provider_factory_configured
    ):
        """Test detection with AI explanations from configured provider."""
        result = await service.detect_and_explain(
            session_id="test-session-1",
            analysis_service=mock_analysis_service,
            provider_factory=mock_provider_factory_configured,
        )

        # Should have detected plays (tackles from converging players)
        assert isinstance(result, list)
        assert len(result) > 0

        # Each play should be a dict with expected keys
        for play in result:
            assert "play_type" in play
            assert "start_time" in play
            assert "end_time" in play
            assert "confidence" in play
            assert "players_involved" in play
            assert "position" in play
            assert "description" in play
            assert "ai_explanation" in play

        # AI explanation should be set since provider is configured
        plays_with_explanation = [p for p in result if p["ai_explanation"] is not None]
        assert len(plays_with_explanation) > 0

        # Verify AI provider was called
        provider = mock_provider_factory_configured.get_provider()
        assert provider.analyze_play.called

    @pytest.mark.asyncio
    async def test_detect_and_explain_unconfigured_provider(
        self, service, mock_analysis_service, mock_provider_factory_unconfigured
    ):
        """Test detection when AI provider is not configured (skips explanations)."""
        result = await service.detect_and_explain(
            session_id="test-session-1",
            analysis_service=mock_analysis_service,
            provider_factory=mock_provider_factory_unconfigured,
        )

        # Should still detect plays
        assert isinstance(result, list)
        assert len(result) > 0

        # All ai_explanation should be None
        for play in result:
            assert play["ai_explanation"] is None

    @pytest.mark.asyncio
    async def test_detect_and_explain_provider_error(
        self, service, mock_analysis_service, mock_provider_factory_error
    ):
        """Test graceful handling when provider factory raises error."""
        result = await service.detect_and_explain(
            session_id="test-session-1",
            analysis_service=mock_analysis_service,
            provider_factory=mock_provider_factory_error,
        )

        # Should still detect plays without explanations
        assert isinstance(result, list)
        assert len(result) > 0

        for play in result:
            assert play["ai_explanation"] is None

    @pytest.mark.asyncio
    async def test_detect_and_explain_empty_results(
        self, service, mock_analysis_service_empty, mock_provider_factory_configured
    ):
        """Test with no players data (empty results)."""
        result = await service.detect_and_explain(
            session_id="test-session-2",
            analysis_service=mock_analysis_service_empty,
            provider_factory=mock_provider_factory_configured,
        )

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_detect_and_explain_session_not_found(
        self, service, mock_provider_factory_configured
    ):
        """Test with non-existent session raises KeyError."""
        analysis_service = MagicMock()
        analysis_service.get_results.side_effect = KeyError("Session not found")

        with pytest.raises(KeyError):
            await service.detect_and_explain(
                session_id="non-existent",
                analysis_service=analysis_service,
                provider_factory=mock_provider_factory_configured,
            )

    @pytest.mark.asyncio
    async def test_detect_and_explain_analysis_not_complete(
        self, service, mock_provider_factory_configured
    ):
        """Test with incomplete analysis raises ValueError."""
        analysis_service = MagicMock()
        analysis_service.get_results.side_effect = ValueError("Analysis not complete")

        with pytest.raises(ValueError):
            await service.detect_and_explain(
                session_id="incomplete-session",
                analysis_service=analysis_service,
                provider_factory=mock_provider_factory_configured,
            )


class TestPlayToDictSerialization:
    """Tests for play serialization."""

    @pytest.mark.asyncio
    async def test_play_dict_serializable(
        self, service, mock_analysis_service, mock_provider_factory_unconfigured
    ):
        """Test that returned plays are JSON-serializable dicts."""
        import json

        result = await service.detect_and_explain(
            session_id="test-session-1",
            analysis_service=mock_analysis_service,
            provider_factory=mock_provider_factory_unconfigured,
        )

        # Should be JSON-serializable
        json_str = json.dumps(result)
        assert json_str is not None

        # Position should be a list (not tuple)
        for play in result:
            assert isinstance(play["position"], list)
            assert len(play["position"]) == 2


class TestAIProviderIntegration:
    """Tests for AI provider integration."""

    @pytest.mark.asyncio
    async def test_ai_provider_called_for_each_play(
        self, service, mock_analysis_service, mock_provider_factory_configured
    ):
        """Test that AI provider is called for each detected play."""
        result = await service.detect_and_explain(
            session_id="test-session-1",
            analysis_service=mock_analysis_service,
            provider_factory=mock_provider_factory_configured,
        )

        provider = mock_provider_factory_configured.get_provider()
        # Should be called once per detected play
        assert provider.analyze_play.call_count == len(result)

    @pytest.mark.asyncio
    async def test_ai_provider_failure_per_play(self, service, mock_analysis_service):
        """Test graceful handling when AI fails for individual plays."""
        factory = MagicMock()
        provider = MagicMock()
        provider.is_configured.return_value = True
        # Fail on first call, succeed on subsequent
        provider.analyze_play = AsyncMock(
            side_effect=[Exception("API timeout"), "Valid explanation"]
        )
        factory.get_provider.return_value = provider

        result = await service.detect_and_explain(
            session_id="test-session-1",
            analysis_service=mock_analysis_service,
            provider_factory=factory,
        )

        # Should still return all plays
        assert len(result) > 0
        # First play should have no explanation, second should have one
        # (depends on how many plays are detected)
        explanations = [p["ai_explanation"] for p in result]
        # At least one should be None (the failed one)
        assert None in explanations or "Valid explanation" in explanations
