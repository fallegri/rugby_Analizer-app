"""AI provider API routes.

Endpoints for interacting with AI providers: analyze, list, switch, and configure.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.adapters.ai.provider_factory import AIProviderFactory
from src.config.settings import Settings, get_settings
from src.core.enums import AIProvider

router = APIRouter(prefix="/api/ai", tags=["ai"])


# --- Request/Response Models ---


class AnalyzeRequest(BaseModel):
    """Request model for AI analysis."""

    prompt: str = Field(..., min_length=1, max_length=10000)
    context: str = Field(default="", max_length=50000)
    provider: Optional[AIProvider] = None


class AnalyzeResponse(BaseModel):
    """Response model for AI analysis."""

    result: str
    provider: str


class SwitchProviderRequest(BaseModel):
    """Request to switch the active AI provider."""

    provider: AIProvider


class UpdateConfigRequest(BaseModel):
    """Request to update AI provider configuration."""

    provider: AIProvider
    api_key: str = Field(..., min_length=1)


class ProviderInfo(BaseModel):
    """Information about an AI provider."""

    name: str
    configured: bool
    active: bool


# --- Dependencies ---


def get_provider_factory(settings: Settings = Depends(get_settings)) -> AIProviderFactory:
    """Dependency that provides the AI provider factory."""
    return AIProviderFactory(settings)


# --- Endpoints ---


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    factory: AIProviderFactory = Depends(get_provider_factory),
):
    """Send a prompt to the configured AI provider for analysis.

    Args:
        request: The analysis request containing prompt and optional context.
        factory: The AI provider factory (injected).

    Returns:
        The AI provider's analysis response.
    """
    try:
        provider = factory.get_provider(request.provider)

        if not provider.is_configured():
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider.get_provider_name()}' is not configured. "
                f"Please set an API key first.",
            )

        result = await provider.analyze_play(request.prompt, request.context)
        return AnalyzeResponse(result=result, provider=provider.get_provider_name())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(
    factory: AIProviderFactory = Depends(get_provider_factory),
):
    """List all available AI providers with their configuration status.

    Returns:
        List of provider information objects.
    """
    providers = factory.list_providers()
    return [ProviderInfo(**p) for p in providers]


@router.put("/provider")
async def switch_provider(
    request: SwitchProviderRequest,
    factory: AIProviderFactory = Depends(get_provider_factory),
):
    """Switch the active AI provider.

    Args:
        request: Contains the provider to switch to.

    Returns:
        Confirmation with the newly active provider name.
    """
    try:
        provider = factory.switch_provider(request.provider)
        return {
            "message": f"Switched to {provider.get_provider_name()}",
            "active_provider": provider.get_provider_name(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/config")
async def update_config(
    request: UpdateConfigRequest,
    factory: AIProviderFactory = Depends(get_provider_factory),
):
    """Update the API key for a specific AI provider at runtime.

    Args:
        request: Contains the provider and new API key.

    Returns:
        Confirmation of the update.
    """
    try:
        factory.update_provider_key(request.provider, request.api_key)
        return {
            "message": f"API key updated for {request.provider.value}",
            "provider": request.provider.value,
            "configured": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
