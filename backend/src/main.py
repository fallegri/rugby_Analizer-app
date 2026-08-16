"""Main application entry point - FastAPI app factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Uses the factory pattern to allow different configurations
    for testing, development, and production environments.
    """
    app = FastAPI(
        title="Rugby Analyzer API",
        description="Rugby video analysis with computer vision and AI",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "rugby-analyzer"}

    return app


# Application instance for uvicorn
app = create_app()
