"""
Service modules for the YouTube Shorts Automation Pipeline.
"""

from .downloader import VideoDownloader
from .branding import VideoBranding
from .metadata_service import MetadataService
from .highlight_detector import HighlightDetector
from .clip_creator import ClipCreator
from .uploader import VideoUploader
from .video_processor import VideoProcessor, ProcessingResult
from .content_manager import ContentManager
from .youtube_api import YouTubeAPI

__all__ = [
    "VideoDownloader",
    "VideoBranding", 
    "MetadataService",
    "HighlightDetector",
    "ClipCreator",
    "VideoUploader",
    "VideoProcessor",
    "ProcessingResult",
    "ContentManager",
    "YouTubeAPI"
]