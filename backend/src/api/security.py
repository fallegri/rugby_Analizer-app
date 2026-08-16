"""Security utilities for API and WebSocket protection.

Includes file upload validation, filename sanitization, WebSocket
origin and connection limiting, and timing-safe comparisons.
"""

import hmac
import logging
import os
import re
import time
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# Magic bytes for supported video formats
MAGIC_BYTES = {
    "mp4": [
        (4, b"ftyp"),
    ],
    "mov": [
        (4, b"ftyp"),
        (4, b"moov"),
    ],
    "avi": [
        (0, b"RIFF"),
    ],
    "mkv": [
        (0, b"\x1a\x45\xdf\xa3"),
    ],
}

# Valid content types for video uploads
VALID_CONTENT_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "application/octet-stream",
}

# WebSocket connection tracking per IP
_ws_connections: dict[str, list[float]] = defaultdict(list)

# Default maximum file size (500MB)
DEFAULT_MAX_FILE_SIZE = 500 * 1024 * 1024


def validate_file_upload(
    content: bytes,
    filename: str,
    content_type: Optional[str] = None,
    max_size: Optional[int] = None,
) -> tuple[bool, str]:
    """Validate a file upload for security.

    Checks magic bytes, content type, and file size against
    configured limits.

    Args:
        content: The raw file bytes.
        filename: Original filename.
        content_type: MIME type from the upload.
        max_size: Maximum allowed file size in bytes.

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    max_size = max_size or (settings.max_file_size_mb * 1024 * 1024)

    # Check file size
    if len(content) > max_size:
        return False, f"File size ({len(content)} bytes) exceeds maximum ({max_size} bytes)"

    # Check file size is non-zero
    if len(content) == 0:
        return False, "File is empty"

    # Validate extension
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext not in MAGIC_BYTES:
        return False, f"Unsupported file extension: .{ext}"

    # Validate content type if provided
    if content_type and content_type not in VALID_CONTENT_TYPES:
        return False, f"Invalid content type: {content_type}"

    # Validate magic bytes
    if not _check_magic_bytes(content, ext):
        return False, f"File content does not match expected format for .{ext}"

    return True, ""


def _check_magic_bytes(content: bytes, extension: str) -> bool:
    """Check if file content matches expected magic bytes for the extension.

    Args:
        content: Raw file bytes.
        extension: File extension (without dot).

    Returns:
        True if magic bytes match, False otherwise.
    """
    if extension not in MAGIC_BYTES:
        return False

    signatures = MAGIC_BYTES[extension]

    for offset, magic in signatures:
        if len(content) > offset + len(magic):
            if content[offset : offset + len(magic)] == magic:
                return True

    return False


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and special characters.

    Removes directory separators, path traversal sequences, and
    characters that could cause issues on various filesystems.

    Args:
        filename: The original filename to sanitize.

    Returns:
        Sanitized filename safe for filesystem use.
    """
    if not filename:
        return "unnamed"

    # Remove path components (prevent traversal)
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove path traversal patterns
    filename = filename.replace("..", "")
    filename = filename.replace("/", "")
    filename = filename.replace("\\", "")

    # Remove special characters, keep only alphanumeric, dots, hyphens, underscores
    filename = re.sub(r"[^\w\-.]", "_", filename)

    # Prevent hidden files
    filename = filename.lstrip(".")

    # Ensure not empty after sanitization
    if not filename:
        return "unnamed"

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    return filename


def validate_websocket_origin(origin: Optional[str]) -> bool:
    """Validate WebSocket connection origin against allowed origins.

    Args:
        origin: The Origin header from the WebSocket handshake.

    Returns:
        True if origin is allowed, False otherwise.
    """
    if origin is None:
        return True

    from src.config.settings import get_settings

    settings = get_settings()
    allowed_origins = settings.cors_origins

    if "*" in allowed_origins:
        return True

    return origin in allowed_origins


def rate_limit_websocket(ip: str, max_connections: int = 5) -> bool:
    """Check if an IP has exceeded the WebSocket connection limit.

    Args:
        ip: The client IP address.
        max_connections: Maximum concurrent connections per IP.

    Returns:
        True if connection is allowed, False if limit exceeded.
    """
    now = time.time()
    # Clean up old entries (connections older than 1 hour)
    _ws_connections[ip] = [
        t for t in _ws_connections[ip] if now - t < 3600
    ]

    if len(_ws_connections[ip]) >= max_connections:
        logger.warning(f"WebSocket rate limit exceeded for IP: {ip}")
        return False

    _ws_connections[ip].append(now)
    return True


def release_websocket_connection(ip: str) -> None:
    """Release a WebSocket connection slot for the given IP.

    Args:
        ip: The client IP address.
    """
    if ip in _ws_connections and _ws_connections[ip]:
        _ws_connections[ip].pop(0)


def reset_ws_connections() -> None:
    """Reset all WebSocket connection tracking. Used for testing."""
    _ws_connections.clear()


def timing_safe_compare(a: str, b: str) -> bool:
    """Perform a constant-time string comparison.

    Prevents timing attacks when comparing API keys or secrets.

    Args:
        a: First string.
        b: Second string.

    Returns:
        True if strings are equal, False otherwise.
    """
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
