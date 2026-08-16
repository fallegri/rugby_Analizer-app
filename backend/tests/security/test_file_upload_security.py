"""Security tests for file upload validation.

Tests that the upload endpoint correctly rejects malicious files,
oversized files, wrong formats, and path traversal attempts.
"""

import io
import struct

import pytest
from fastapi.testclient import TestClient

from src.api.security import sanitize_filename, validate_file_upload
from src.main import create_app


@pytest.fixture
def app():
    """Create a test app instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def valid_mp4_content():
    """Create valid MP4 content with proper magic bytes."""
    content = bytearray(1024)
    content[0:4] = struct.pack(">I", 20)
    content[4:8] = b"ftyp"
    content[8:12] = b"isom"
    return bytes(content)


@pytest.fixture
def valid_avi_content():
    """Create valid AVI content with RIFF magic bytes."""
    content = bytearray(1024)
    content[0:4] = b"RIFF"
    content[8:12] = b"AVI "
    return bytes(content)


@pytest.fixture
def valid_mkv_content():
    """Create valid MKV content with EBML magic bytes."""
    content = bytearray(1024)
    content[0:4] = b"\x1a\x45\xdf\xa3"
    return bytes(content)


class TestMagicByteValidation:
    """Tests for magic byte validation of uploaded files."""

    def test_reject_php_script_renamed_to_mp4(self, client):
        """Test that a PHP script renamed to .mp4 is rejected."""
        php_content = b"<?php echo 'hacked'; ?>" + b"\x00" * 100
        response = client.post(
            "/api/video/upload",
            files={"file": ("exploit.mp4", io.BytesIO(php_content), "video/mp4")},
        )
        assert response.status_code == 400
        assert "content does not match" in response.json()["detail"].lower()

    def test_reject_exe_renamed_to_mp4(self, client):
        """Test that an executable renamed to .mp4 is rejected."""
        exe_content = b"MZ" + b"\x00" * 500
        response = client.post(
            "/api/video/upload",
            files={"file": ("malware.mp4", io.BytesIO(exe_content), "video/mp4")},
        )
        assert response.status_code == 400

    def test_reject_html_renamed_to_avi(self, client):
        """Test that HTML content renamed to .avi is rejected."""
        html_content = b"<html><body><script>alert('xss')</script></body></html>" + b"\x00" * 100
        response = client.post(
            "/api/video/upload",
            files={"file": ("page.avi", io.BytesIO(html_content), "video/x-msvideo")},
        )
        assert response.status_code == 400

    def test_accept_valid_mp4(self, client, valid_mp4_content):
        """Test that valid MP4 file is accepted."""
        response = client.post(
            "/api/video/upload",
            files={"file": ("video.mp4", io.BytesIO(valid_mp4_content), "video/mp4")},
        )
        assert response.status_code == 201

    def test_accept_valid_avi(self, client, valid_avi_content):
        """Test that valid AVI file is accepted."""
        response = client.post(
            "/api/video/upload",
            files={"file": ("video.avi", io.BytesIO(valid_avi_content), "video/x-msvideo")},
        )
        assert response.status_code == 201

    def test_accept_valid_mkv(self, client, valid_mkv_content):
        """Test that valid MKV file is accepted."""
        response = client.post(
            "/api/video/upload",
            files={"file": ("video.mkv", io.BytesIO(valid_mkv_content), "video/x-matroska")},
        )
        assert response.status_code == 201


class TestFileSizeValidation:
    """Tests for file size limits."""

    def test_reject_oversized_file(self):
        """Test that validate_file_upload rejects oversized files."""
        content = b"\x00" * 2000
        is_valid, error = validate_file_upload(
            content=content,
            filename="big.mp4",
            max_size=1000,
        )
        assert not is_valid
        assert "exceeds maximum" in error.lower()

    def test_reject_empty_file(self, client):
        """Test that empty file is rejected."""
        response = client.post(
            "/api/video/upload",
            files={"file": ("empty.mp4", io.BytesIO(b""), "video/mp4")},
        )
        assert response.status_code == 400


class TestExtensionValidation:
    """Tests for file extension validation."""

    def test_reject_unsupported_extension(self, client):
        """Test that unsupported extensions are rejected."""
        content = b"fake content"
        response = client.post(
            "/api/video/upload",
            files={"file": ("test.exe", io.BytesIO(content), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()

    def test_reject_php_extension(self, client):
        """Test that PHP extension is rejected."""
        response = client.post(
            "/api/video/upload",
            files={"file": ("shell.php", io.BytesIO(b"<?php ?>"), "text/plain")},
        )
        assert response.status_code == 400

    def test_reject_no_extension(self, client):
        """Test that files without extension are rejected."""
        response = client.post(
            "/api/video/upload",
            files={"file": ("noextension", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 400


class TestPathTraversal:
    """Tests for path traversal in filenames."""

    def test_path_traversal_double_dots(self):
        """Test that ../../../etc/passwd is sanitized."""
        result = sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_path_traversal_backslash(self):
        """Test that backslash path traversal is sanitized."""
        result = sanitize_filename("..\\..\\windows\\system32\\config")
        assert "\\" not in result
        assert ".." not in result

    def test_null_byte_injection(self):
        """Test that null bytes are removed from filename."""
        result = sanitize_filename("video.mp4\x00.php")
        assert "\x00" not in result

    def test_hidden_file_prevention(self):
        """Test that leading dots are removed (prevent hidden files)."""
        result = sanitize_filename(".htaccess")
        assert not result.startswith(".")

    def test_special_characters_removed(self):
        """Test that special characters are replaced."""
        result = sanitize_filename("video<>|:*.mp4")
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result
        assert ":" not in result
        assert "*" not in result

    def test_normal_filename_preserved(self):
        """Test that normal filenames are preserved."""
        result = sanitize_filename("my_video-2024.mp4")
        assert result == "my_video-2024.mp4"

    def test_empty_filename_returns_unnamed(self):
        """Test that empty filename gets default name."""
        result = sanitize_filename("")
        assert result == "unnamed"

    def test_long_filename_truncated(self):
        """Test that very long filenames are truncated."""
        long_name = "a" * 300 + ".mp4"
        result = sanitize_filename(long_name)
        assert len(result) <= 255
