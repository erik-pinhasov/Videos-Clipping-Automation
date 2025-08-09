"""
Core modules for the YouTube Shorts Automation Pipeline.
"""

from .logger import setup_logging, get_logger, LoggerMixin, log_function_call
from .exceptions import (
    PipelineError,
    ConfigurationError,
    VideoProcessingError,
    DownloadError,
    BrandingError,
    HighlightDetectionError,
    ClipCreationError,
    MetadataError,
    UploadError,
    YouTubeUploadError,
    RumbleUploadError,
    APIError,
    YouTubeAPIError,
    OpenAIAPIError,
    ResourceError,
    ValidationError,
    handle_pipeline_error
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "LoggerMixin",
    "log_function_call",
    
    # Exceptions
    "PipelineError",
    "ConfigurationError", 
    "VideoProcessingError",
    "DownloadError",
    "BrandingError",
    "HighlightDetectionError",
    "ClipCreationError",
    "MetadataError",
    "UploadError",
    "YouTubeUploadError",
    "RumbleUploadError",
    "APIError",
    "YouTubeAPIError",
    "OpenAIAPIError",
    "ResourceError",
    "ValidationError",
    "handle_pipeline_error"
]