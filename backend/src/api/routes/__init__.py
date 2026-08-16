"""API routes package."""

from src.api.routes.ai import router as ai_router
from src.api.routes.health import router as health_router

__all__ = ["health_router", "ai_router"]
