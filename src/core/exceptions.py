"""
ALL exceptions for the YouTube Shorts automation system - COMPLETE LIST.
"""


class AutomationError(Exception):
    """Base exception for automation errors."""
    pass


class PipelineError(AutomationError):
    """Error in the processing pipeline."""
    pass


class VideoProcessingError(AutomationError):
    """Error during video processing."""
    pass


class DownloadError(AutomationError):
    """Error during video download."""
    pass


class UploadError(AutomationError):
    """Base class for upload errors."""
    pass


class YouTubeUploadError(UploadError):
    """Error during YouTube upload."""
    pass


class YouTubeAPIError(UploadError):
    """Error with YouTube API."""
    pass


class RumbleUploadError(UploadError):
    """Error during Rumble upload."""
    pass


class MetadataError(AutomationError):
    """Error during metadata generation."""
    pass


class OpenAIError(AutomationError):
    """Error with OpenAI API."""
    pass


class QuotaExceededError(AutomationError):
    """API quota exceeded."""
    pass


class HighlightDetectionError(AutomationError):
    """Error during highlight detection."""
    pass


class ClipCreationError(AutomationError):
    """Error during clip creation."""
    pass


class ContentDiscoveryError(AutomationError):
    """Error during content discovery."""
    pass


class ConfigurationError(AutomationError):
    """Configuration error."""
    pass


class BrandingError(AutomationError):
    """Error during video branding."""
    pass


class TranscriptionError(AutomationError):
    """Error during transcription."""
    pass


class ValidationError(AutomationError):
    """Validation error."""
    pass


class NetworkError(AutomationError):
    """Network-related error."""
    pass


class FileProcessingError(AutomationError):
    """File processing error."""
    pass


class APIError(AutomationError):
    """Generic API error."""
    pass


class RateLimitError(AutomationError):
    """Rate limit exceeded."""
    pass


class AuthenticationError(AutomationError):
    """Authentication error."""
    pass


class PermissionError(AutomationError):
    """Permission error."""
    pass


class ResourceNotFoundError(AutomationError):
    """Resource not found error."""
    pass


class TimeoutError(AutomationError):
    """Operation timeout error."""
    pass