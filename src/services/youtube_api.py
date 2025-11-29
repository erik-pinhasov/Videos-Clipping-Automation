import config
from datetime import datetime
from src.core.logger import get_logger
from src.core.exceptions import YouTubeAPIError


class YouTubeAPI:
    """YouTube API wrapper for video operations."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        self._api_calls_count = 0
        self._last_reset_time = datetime.now()
        
        # Try to initialize actual YouTube API
        self.youtube_service = None
        self._initialize_youtube_api()
    
    def _initialize_youtube_api(self):
        """Initialize YouTube Data API if credentials are available."""
        try:
            if not self.config.YOUTUBE_API_KEY:
                self.logger.warning("YouTube API key not configured, using mock data")
                return
            
            # Try to import and initialize YouTube API
            try:
                from googleapiclient.discovery import build
                self.youtube_service = build('youtube', 'v3', developerKey=self.config.YOUTUBE_API_KEY)
                self.logger.info("YouTube Data API initialized successfully")
            except ImportError:
                self.logger.warning("Google API client not installed, using mock data")
            except Exception as e:
                self.logger.warning(f"YouTube API initialization failed: {e}, using mock data")
                
        except Exception as e:
            self.logger.error(f"Error initializing YouTube API: {e}")

    def _parse_duration(self, duration_str: str) -> int:
        """Parse YouTube duration format (PT1H2M3S) to seconds."""
        try:
            import re
            pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
            match = pattern.match(duration_str)
            
            if not match:
                return 0
            
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            
            return hours * 3600 + minutes * 60 + seconds
            
        except Exception:
            return 0
    
    def _check_rate_limits(self) -> None:
        """Check and enforce API rate limits."""
        now = datetime.now()
        
        # Reset counter daily
        if (now - self._last_reset_time).days >= 1:
            self._api_calls_count = 0
            self._last_reset_time = now
            self.logger.info("Daily API quota reset")
        
        # Check quota limits
        max_calls = getattr(self.config, 'YOUTUBE_API_DAILY_QUOTA', 1000)
        if self._api_calls_count >= max_calls:
            raise YouTubeAPIError("YouTube API daily quota exceeded")
