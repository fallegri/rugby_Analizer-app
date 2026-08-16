"""Core domain enumerations for the Rugby Analyzer system."""

from enum import Enum


class TrackingMode(str, Enum):
    """Tracking modes available for video analysis."""

    SINGLE_PLAYER = "single_player"
    BALL_CARRIER = "ball_carrier"
    BALL_ONLY = "ball_only"
    GROUP_TRACKING = "group_tracking"


class AnalysisStatus(str, Enum):
    """Status of an analysis session."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AIProvider(str, Enum):
    """Supported AI provider backends."""

    NVIDIA = "nvidia"
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class VideoStatus(str, Enum):
    """Status of a video in the processing pipeline."""

    UPLOADED = "uploaded"
    CALIBRATING = "calibrating"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
