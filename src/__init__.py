"""
YouTube Shorts Automation Pipeline

A comprehensive automation system for processing videos from YouTube channels,
adding branding, creating highlight clips, and uploading to multiple platforms.
"""

__version__ = "1.0.0"
__author__ = "Erik P"
__description__ = "YouTube Shorts Automation Pipeline"

from src.core.logger import setup_logging, get_logger
from src.core.exceptions import (
    PipelineError,
    VideoProcessingError,
    DownloadError,
    UploadError,
    MetadataError,
    ConfigurationError
)

__all__ = [
    "setup_logging",
    "get_logger", 
    "PipelineError",
    "VideoProcessingError",
    "DownloadError",
    "UploadError",
    "MetadataError",
    "ConfigurationError"
]