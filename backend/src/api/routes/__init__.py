"""API routes package."""

from src.api.routes.ai import router as ai_router
from src.api.routes.calibration import router as calibration_router
from src.api.routes.health import router as health_router
from src.api.routes.video import router as video_router

__all__ = ["health_router", "ai_router", "video_router", "calibration_router"]
