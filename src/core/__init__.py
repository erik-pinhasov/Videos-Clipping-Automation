"""Core utilities for YouTube to Rumble automation."""

from .logger import setup_logging, get_logger
from .exceptions import (
    AutomationError,
    VideoProcessingError,
    DownloadError,
    UploadError,
    YouTubeUploadError,
    YouTubeAPIError,
    RumbleUploadError,
    MetadataError,
    OpenAIError,
    QuotaExceededError,
    HighlightDetectionError,
    ClipCreationError,
    ContentDiscoveryError,
    ConfigurationError,
    BrandingError,
    TranscriptionError
)

__all__ = [
    # Logging
    'setup_logging',
    'get_logger',
    # Base exceptions
    'AutomationError',
    # Processing exceptions
    'VideoProcessingError',
    'DownloadError',
    'ContentDiscoveryError',
    'BrandingError',
    'HighlightDetectionError',
    'ClipCreationError',
    'TranscriptionError',
    # Upload exceptions
    'UploadError',
    'YouTubeUploadError',
    'YouTubeAPIError',
    'RumbleUploadError',
    # AI/API exceptions
    'MetadataError',
    'OpenAIError',
    'QuotaExceededError',
    # Config exceptions
    'ConfigurationError'
]