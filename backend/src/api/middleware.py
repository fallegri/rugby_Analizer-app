"""API middleware for CORS, rate limiting, and authentication.

Provides in-memory token bucket rate limiting and API key authentication.
"""

import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory token bucket rate limiter middleware.

    Limits requests per client IP within a configurable time window.
    Uses a simple token bucket algorithm without external dependencies.
    """

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if a client has exceeded the rate limit."""
        now = time.time()
        window_start = now - self.window_seconds

        # Remove expired timestamps
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip] if ts > window_start
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return True

        self._requests[client_ip].append(now)
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting."""
        # Skip rate limiting for health checks and docs
        if request.url.path in ("/api/health", "/api/docs", "/api/redoc", "/openapi.json"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        if self._is_rate_limited(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        response = await call_next(request)
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate incoming requests.

    Performs basic input validation and security checks.
    """

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate request before processing."""
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )

        response = await call_next(request)
        return response


def require_api_key(api_key_header: str = "X-API-Key", valid_keys: list[str] | None = None):
    """Dependency for API key authentication on protected endpoints.

    Args:
        api_key_header: The header name containing the API key.
        valid_keys: List of valid API keys. If None, any non-empty key is accepted.

    Returns:
        A FastAPI dependency function.
    """

    async def verify_api_key(request: Request) -> str:
        key = request.headers.get(api_key_header)
        if not key:
            raise HTTPException(
                status_code=401,
                detail="Missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if valid_keys is not None and key not in valid_keys:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key",
            )

        return key

    return verify_api_key
