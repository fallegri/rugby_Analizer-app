"""Shared test fixtures for the Rugby Analyzer backend."""

import os

import pytest
from fastapi.testclient import TestClient

# Set debug mode for tests to bypass secret key validation
os.environ.setdefault("DEBUG", "true")

from src.main import create_app


@pytest.fixture
def app():
    """Create a test FastAPI application instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI application."""
    return TestClient(app)
