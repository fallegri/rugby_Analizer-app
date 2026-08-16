"""Main application entry point - FastAPI app factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import RateLimitMiddleware, RequestValidationMiddleware
from src.api.routes.ai import router as ai_router
from src.api.routes.analysis import router as analysis_router
from src.api.routes.calibration import router as calibration_router
from src.api.routes.health import router as health_router
from src.api.routes.video import router as video_router
from src.api.websocket import router as ws_router
from src.config.settings import get_settings
from src.services.analysis_service import AnalysisService
from src.services.background_tasks import BackgroundTaskManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events for resource initialization
    and cleanup (database connections, model loading, etc.).
    """
    # Startup
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Default AI provider: {settings.default_ai_provider}")

    yield

    # Shutdown
    logger.info("Shutting down Rugby Analyzer API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Uses the factory pattern to allow different configurations
    for testing, development, and production environments.
    """
    settings = get_settings()

    app = FastAPI(
        title="Rugby Analyzer API",
        description="Rugby video analysis with computer vision and AI",
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    # Add request validation middleware
    app.add_middleware(RequestValidationMiddleware)

    # Include routers
    app.include_router(health_router)
    app.include_router(ai_router)
    app.include_router(video_router)
    app.include_router(calibration_router)
    app.include_router(analysis_router)
    app.include_router(ws_router)

    # Initialize services and attach to app state
    app.state.analysis_service = AnalysisService()
    app.state.background_task_manager = BackgroundTaskManager()

    return app


# Application instance for uvicorn
app = create_app()
