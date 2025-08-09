"""
Custom exception classes for the YouTube Shorts Automation Pipeline.
"""

from typing import Optional, Any


class PipelineError(Exception):
    """Base exception for pipeline-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ConfigurationError(PipelineError):
    """Raised when there's a configuration problem."""
    pass


class VideoProcessingError(PipelineError):
    """Raised when video processing operations fail."""
    pass


class DownloadError(VideoProcessingError):
    """Raised when video download fails."""
    pass


class BrandingError(VideoProcessingError):
    """Raised when logo branding fails."""
    pass


class HighlightDetectionError(VideoProcessingError):
    """Raised when highlight detection fails."""
    pass


class ClipCreationError(VideoProcessingError):
    """Raised when clip creation fails."""
    pass


class MetadataError(PipelineError):
    """Raised when metadata generation fails."""
    pass


class UploadError(PipelineError):
    """Raised when upload operations fail."""
    
    def __init__(self, message: str, platform: Optional[str] = None, 
                 retry_possible: bool = True, **kwargs):
        super().__init__(message, **kwargs)
        self.platform = platform
        self.retry_possible = retry_possible


class YouTubeUploadError(UploadError):
    """Specific exception for YouTube upload failures."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, platform="YouTube", **kwargs)


class RumbleUploadError(UploadError):
    """Specific exception for Rumble upload failures."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, platform="Rumble", **kwargs)


class APIError(PipelineError):
    """Raised when external API calls fail."""
    
    def __init__(self, message: str, api_name: Optional[str] = None, 
                 status_code: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.api_name = api_name
        self.status_code = status_code


class YouTubeAPIError(APIError):
    """Specific exception for YouTube API failures."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, api_name="YouTube API", **kwargs)


class OpenAIAPIError(APIError):
    """Specific exception for OpenAI API failures."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, api_name="OpenAI API", **kwargs)


class ResourceError(PipelineError):
    """Raised when there are resource-related problems (disk space, file permissions, etc.)."""
    pass


class ValidationError(PipelineError):
    """Raised when data validation fails."""
    pass


def handle_pipeline_error(func):
    """Decorator to handle and log pipeline errors gracefully."""
    import functools
    from src.core.logger import get_logger
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        try:
            return func(*args, **kwargs)
        except PipelineError as e:
            logger.error(f"Pipeline error in {func.__name__}: {e}")
            if e.details:
                logger.debug(f"Error details: {e.details}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            raise PipelineError(f"Unexpected error in {func.__name__}: {str(e)}")
    
    return wrapper