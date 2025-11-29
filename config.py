import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: python-dotenv not installed. Run: pip install python-dotenv")
    def load_dotenv():
        pass

class Config:
    """Configuration for YouTube to Rumble automation pipeline."""
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Basic settings
        self.BASE_DIR = Path(__file__).parent
        self.DOWNLOAD_DIR = "media/downloads"
        self.CLIPS_DIR = "media/clips"
        self.LOGOS_DIR = "media/assets"

        # API Keys
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in the .env file")

        self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        if not self.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is not set in the .env file")

        # Rumble Credentials
        self.RUMBLE_EMAIL = os.getenv("RUMBLE_EMAIL")
        if not self.RUMBLE_EMAIL:
            raise ValueError("RUMBLE_EMAIL is not set in the .env file")

        self.RUMBLE_PASSWORD = os.getenv("RUMBLE_PASSWORD")
        if not self.RUMBLE_PASSWORD:
            raise ValueError("RUMBLE_PASSWORD is not set in the .env file")

        self.RUMBLE_USERNAME = os.getenv("RUMBLE_USERNAME")
        if not self.RUMBLE_USERNAME:
            raise ValueError("RUMBLE_USERNAME is not set in the .env file")

        # YouTube OAuth
        self.YOUTUBE_CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "credentials/client_secret.json")

        # Processing limits
        self.MAX_VIDEOS_PER_SESSION = int(os.getenv("MAX_VIDEOS_PER_SESSION", "4"))
        
        # Subtitles
        self.SUBTITLES_MODE = os.getenv("SUBTITLES_MODE", "exact").lower()
        self.WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
        
        # Rumble upload settings
        self.RUMBLE_UPLOAD_METHOD = os.getenv("RUMBLE_UPLOAD_METHOD", "playwright").lower()
        self.RUMBLE_UPLOAD_ASYNC = os.getenv("RUMBLE_UPLOAD_ASYNC", "true").lower() in ["1", "true", "yes"]
        self.RUMBLE_UPLOAD_TIMEOUT_MS = int(os.getenv("RUMBLE_UPLOAD_TIMEOUT_MS", str(60 * 60 * 3 * 1000)))
        
        # Playwright browser automation
        self.PLAYWRIGHT_BROWSER = os.getenv("PLAYWRIGHT_BROWSER", "chromium").lower()
        self.PLAYWRIGHT_AUTO_INSTALL = os.getenv("PLAYWRIGHT_AUTO_INSTALL", "true").lower() in ["1", "true", "yes"]
        self.PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in ["1", "true", "yes"]
        self.PLAYWRIGHT_SLOWMO_MS = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0"))

        # YouTube upload settings
        self.YOUTUBE_MADE_FOR_KIDS = os.getenv("YOUTUBE_MADE_FOR_KIDS", "false").lower() in ["1", "true", "yes"]
        self.YOUTUBE_FORCE_SHORTS_HASHTAG = os.getenv("YOUTUBE_FORCE_SHORTS_HASHTAG", "true").lower() in ["1", "true", "yes"]
        self.YOUTUBE_MIN_UPLOAD_INTERVAL = int(os.getenv("YOUTUBE_MIN_UPLOAD_INTERVAL", "10"))
        self.YOUTUBE_UPLOAD_MAX_RETRIES = int(os.getenv("YOUTUBE_UPLOAD_MAX_RETRIES", "3"))
        self.YOUTUBE_UPLOAD_RETRY_BACKOFF_BASE = float(os.getenv("YOUTUBE_UPLOAD_RETRY_BACKOFF_BASE", "2.0"))
        
        # Cleanup behavior
        self.DELETE_CLIP_AFTER_UPLOAD = os.getenv("DELETE_CLIP_AFTER_UPLOAD", "true").lower() in ["1", "true", "yes"]
        self.CLEANUP_DELETE_BRANDED = os.getenv("CLEANUP_DELETE_BRANDED", "true").lower() in ["1", "true", "yes"]
        self.CLEANUP_DELETE_ORIGINAL_DOWNLOAD = os.getenv("CLEANUP_DELETE_ORIGINAL_DOWNLOAD", "true").lower() in ["1", "true", "yes"]
        
        # Download quality
        self.DOWNLOAD_MAX_HEIGHT = int(os.getenv("DOWNLOAD_MAX_HEIGHT", "2160"))
        self.DOWNLOAD_PREFER_AV1 = os.getenv("DOWNLOAD_PREFER_AV1", "true").lower() in ["1", "true", "yes"]
        self.DOWNLOAD_MERGE_FORMAT = os.getenv("DOWNLOAD_MERGE_FORMAT", "mkv").lower()

        # Metadata generation
        self.METADATA_USE_ORIGINAL_TITLE = os.getenv("METADATA_USE_ORIGINAL_TITLE", "false").lower() in ["1", "true", "yes"]
        self.METADATA_FALLBACK_TITLE = os.getenv("METADATA_FALLBACK_TITLE", "Amazing Nature Moment")

        # Logo configuration - customize per channel
        # Format: 'channel_id': {'logo_path': 'path/to/logo.png', 'location': 'top_left', 'spacing_x': px, 'spacing_y': px}
        self.CHANNEL_LOGOS = os.getenv("CHANNEL_LOGOS_JSON", None)
        if self.CHANNEL_LOGOS:
            import json
            self.CHANNEL_LOGOS = json.loads(self.CHANNEL_LOGOS)
        else:
            # Default logo configuration
            self.CHANNEL_LOGOS = {
                'default': {
                    'logo_path': 'media/assets/logo.png',
                    'location': 'top_right',
                    'spacing_x': 20,
                    'spacing_y': 20,
                    'primary_category': 'wildlife',
                    'content_tags': ['nature', 'wildlife', 'animals']
                }
            }

        # Create directories
        for directory in [self.DOWNLOAD_DIR, self.CLIPS_DIR, self.LOGOS_DIR]:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        # YouTube channels to monitor - customize these
        self.YOUTUBE_CHANNELS = self._load_youtube_channels()

        # Video selection criteria
        self.MAX_VIDEOS_TOTAL = int(os.getenv("MAX_VIDEOS_TOTAL", "4"))
        self.MIN_VIDEO_DURATION = int(os.getenv("MIN_VIDEO_DURATION", "1800"))  # 30 minutes
        self.MAX_VIDEO_DURATION = int(os.getenv("MAX_VIDEO_DURATION", "18000"))  # 5 hours
        self.MAX_VIDEO_AGE_DAYS = int(os.getenv("MAX_VIDEO_AGE_DAYS", "365"))  # 1 year
    
    def _load_youtube_channels(self):
        """Load YouTube channels from environment or use defaults."""
        channels_json = os.getenv("YOUTUBE_CHANNELS_JSON", None)
        if channels_json:
            import json
            return json.loads(channels_json)
        
        # Example default channels (Creative Commons content)
        return {
            'example_channel': 'https://www.youtube.com/@examplechannel/videos'
        }
    
    def get_fallback_metadata(self, channel: str, original_title: str = None):
        """Get fallback metadata when AI generation fails."""
        return {
            'title': original_title or self.METADATA_FALLBACK_TITLE,
            'description': 'Amazing nature and wildlife content. Subscribe for more!',
            'tags': ['nature', 'wildlife', 'shorts'],
            'category_id': '15',
            'privacy_status': 'public'
        }
        
        print("✅ Config initialized successfully")