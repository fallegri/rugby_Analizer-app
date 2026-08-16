"""Storage adapter for file and result persistence.

Provides interface-based storage with local filesystem implementation.
Follows hexagonal architecture (ports and adapters) pattern.
"""

import json
import logging
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class StoragePort(ABC):
    """Abstract storage interface for file operations.

    Defines the contract for storage adapters, enabling
    swapping between local, S3, GCS, etc.
    """

    @abstractmethod
    def save_file(self, content: bytes, filename: str) -> str:
        """Save binary file content.

        Args:
            content: File bytes.
            filename: Original filename.

        Returns:
            Unique file ID.
        """
        ...

    @abstractmethod
    def get_file_path(self, file_id: str) -> Optional[Path]:
        """Get the filesystem path for a stored file.

        Args:
            file_id: The unique file ID.

        Returns:
            Path object or None if not found.
        """
        ...

    @abstractmethod
    def delete_file(self, file_id: str) -> bool:
        """Delete a stored file.

        Args:
            file_id: The unique file ID.

        Returns:
            True if deleted, False if not found.
        """
        ...

    @abstractmethod
    def save_json(self, file_id: str, data: dict[str, Any]) -> None:
        """Save JSON data to storage.

        Args:
            file_id: Identifier for the JSON file.
            data: Dictionary to serialize.
        """
        ...

    @abstractmethod
    def load_json(self, file_id: str) -> Optional[dict[str, Any]]:
        """Load JSON data from storage.

        Args:
            file_id: Identifier for the JSON file.

        Returns:
            Deserialized dict or None if not found.
        """
        ...


class LocalStorageAdapter(StoragePort):
    """Local filesystem storage adapter.

    Stores videos in a configurable base directory and results
    as JSON files in a results subdirectory.
    """

    def __init__(self, base_path: str = "uploads"):
        """Initialize local storage with base directory.

        Args:
            base_path: Base directory for all stored files.
        """
        self._base_path = Path(base_path)
        self._videos_path = self._base_path / "videos"
        self._results_path = self._base_path / "results"

        # Create directories
        self._videos_path.mkdir(parents=True, exist_ok=True)
        self._results_path.mkdir(parents=True, exist_ok=True)

    def save_file(self, content: bytes, filename: str) -> str:
        """Save a binary file to local storage.

        Args:
            content: File bytes.
            filename: Original filename (used for extension).

        Returns:
            Unique file ID.
        """
        file_id = str(uuid4())
        ext = Path(filename).suffix.lower()
        dest = self._videos_path / f"{file_id}{ext}"

        dest.write_bytes(content)
        logger.info(f"Saved file {file_id} ({len(content)} bytes)")
        return file_id

    def save_video(self, content: bytes, filename: str) -> str:
        """Save a video file to local storage.

        Args:
            content: Video file bytes.
            filename: Original filename.

        Returns:
            Unique video ID.
        """
        return self.save_file(content, filename)

    def get_file_path(self, file_id: str) -> Optional[Path]:
        """Get the filesystem path for a stored file.

        Args:
            file_id: The unique file ID.

        Returns:
            Path object or None if not found.
        """
        for path in self._videos_path.iterdir():
            if path.stem == file_id:
                return path
        return None

    def get_video_path(self, video_id: str) -> Optional[Path]:
        """Get the path to a stored video.

        Args:
            video_id: The video's unique ID.

        Returns:
            Path to the video file or None if not found.
        """
        return self.get_file_path(video_id)

    def delete_file(self, file_id: str) -> bool:
        """Delete a stored file.

        Args:
            file_id: The unique file ID.

        Returns:
            True if deleted, False if not found.
        """
        path = self.get_file_path(file_id)
        if path and path.exists():
            path.unlink()
            logger.info(f"Deleted file: {file_id}")
            return True
        return False

    def delete_video(self, video_id: str) -> bool:
        """Delete a stored video.

        Args:
            video_id: The video's unique ID.

        Returns:
            True if deleted, False if not found.
        """
        return self.delete_file(video_id)

    def save_json(self, file_id: str, data: dict[str, Any]) -> None:
        """Save JSON data to the results directory.

        Args:
            file_id: Identifier for the JSON file.
            data: Dictionary to serialize.
        """
        dest = self._results_path / f"{file_id}.json"
        dest.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Saved JSON results: {file_id}")

    def save_results(self, session_id: str, results: dict[str, Any]) -> None:
        """Save analysis results for a session.

        Args:
            session_id: The analysis session ID.
            results: Results dictionary to persist.
        """
        self.save_json(session_id, results)

    def load_json(self, file_id: str) -> Optional[dict[str, Any]]:
        """Load JSON data from the results directory.

        Args:
            file_id: Identifier for the JSON file.

        Returns:
            Deserialized dict or None if not found.
        """
        path = self._results_path / f"{file_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def load_results(self, session_id: str) -> Optional[dict[str, Any]]:
        """Load analysis results for a session.

        Args:
            session_id: The analysis session ID.

        Returns:
            Results dictionary or None if not found.
        """
        return self.load_json(session_id)
