from pathlib import Path
from dotenv import load_dotenv
import os

class Config:
    """Simple configuration."""
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Basic settings
        self.BASE_DIR = Path(__file__).parent
        self.DOWNLOAD_DIR = "media/downloads"
        self.CLIPS_DIR = "media/clips"
        self.LOGOS_DIR = "media/assets"

        # OpenAI API Key
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in the .env file")

        # No Hugging Face token required anymore (we rely on OpenAI and local analysis)
        self.HUGGING_FACE_TOKEN = os.getenv("HUGGING_FACE_TOKEN", None)

        self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        if not self.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is not set in the .env file")

        self.RUMBLE_EMAIL = os.getenv("RUMBLE_EMAIL")
        if not self.RUMBLE_EMAIL:
            raise ValueError("RUMBLE_EMAIL is not set in the .env file")

        self.RUMBLE_PASSWORD = os.getenv("RUMBLE_PASSWORD")
        if not self.RUMBLE_PASSWORD:
            raise ValueError("RUMBLE_PASSWORD is not set in the .env file")

        self.RUMBLE_USERNAME = os.getenv("RUMBLE_USERNAME")
        if not self.RUMBLE_USERNAME:
            raise ValueError("RUMBLE_USERNAME is not set in the .env file")

        self.YOUTUBE_CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_FILE")
        if not self.YOUTUBE_CLIENT_SECRET_FILE:
            raise ValueError("YOUTUBE_CLIENT_SECRET_FILE is not set in the .env file")

        self.MAX_VIDEOS_PER_SESSION = 4
        # Subtitles control: 'exact' to use narrator's speech segments (OpenAI Whisper), 'off' to skip subtitles
        self.SUBTITLES_MODE = os.getenv("SUBTITLES_MODE", "exact").lower()
        # Whisper model selection (e.g., whisper-1, gpt-4o-transcribe, etc.)
        self.WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
        # Playwright settings
        self.RUMBLE_UPLOAD_METHOD = os.getenv("RUMBLE_UPLOAD_METHOD", "playwright").lower()
        self.PLAYWRIGHT_BROWSER = os.getenv("PLAYWRIGHT_BROWSER", "chromium").lower()
        self.PLAYWRIGHT_AUTO_INSTALL = os.getenv("PLAYWRIGHT_AUTO_INSTALL", "true").lower() in ["1", "true", "yes"]
        self.PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in ["1", "true", "yes"]
        self.PLAYWRIGHT_SLOWMO_MS = int(os.getenv("PLAYWRIGHT_SLOWMO_MS", "0"))
        self.RUMBLE_UPLOAD_TIMEOUT_MS = int(os.getenv("RUMBLE_UPLOAD_TIMEOUT_MS", str(60 * 60 * 1000)))

        self.OPENAI_DAILY_LIMIT = 10000
        self.HUGGING_FACE_DAILY_LIMIT = 5000

        # YouTube settings
        self.YOUTUBE_MADE_FOR_KIDS = os.getenv("YOUTUBE_MADE_FOR_KIDS", "false").lower() in ["1", "true", "yes"]
        self.YOUTUBE_FORCE_SHORTS_HASHTAG = os.getenv("YOUTUBE_FORCE_SHORTS_HASHTAG", "true").lower() in ["1", "true", "yes"]
        # Cleanup behavior
        self.DELETE_CLIP_AFTER_UPLOAD = os.getenv("DELETE_CLIP_AFTER_UPLOAD", "true").lower() in ["1", "true", "yes"]
        self.CLEANUP_DELETE_BRANDED = os.getenv("CLEANUP_DELETE_BRANDED", "true").lower() in ["1", "true", "yes"]
        self.CLEANUP_DELETE_ORIGINAL_DOWNLOAD = os.getenv("CLEANUP_DELETE_ORIGINAL_DOWNLOAD", "true").lower() in ["1", "true", "yes"]

        # Channel-specific logo configurations
        self.CHANNEL_LOGOS = {
            'naturesmomentstv': {
                'logo_path': 'media/assets/naturesmomentstv.png',
                'location': 'top_left',
                'spacing_x': 17,
                'spacing_y': 15,
                'primary_category': 'wildlife',
                'content_tags': ['nature', 'wildlife', 'animals', 'beautiful']
            },
            'navwildanimaldocumentary': {
                'logo_path': 'media/assets/navwildanimaldocumentary.png', 
                'location': 'top_left',
                'spacing_x': 14,
                'spacing_y': 44,
                'primary_category': 'wildlife',
                'content_tags': ['wildlife', 'animals', 'nature', 'beautiful']
            },
            'wildnatureus2024': {
                'logo_path': 'media/assets/wildnatureus2024.png',
                'location': 'top_right', 
                'spacing_x': 370,
                'spacing_y': 200,
                'primary_category': 'wildlife',
                'content_tags': ['wildlife', 'nature', 'animals', 'beautiful']
            },
            'ScenicScenes': {
                'logo_path': 'media/assets/ScenicScenes.png',
                'location': 'bottom_left',
                'spacing_x': 5,
                'spacing_y': 7,
                'primary_category': 'wildlife',
                'content_tags': ['wildlife', 'nature', 'animals', 'beautiful']
            }
        }

        # Create directories
        for directory in [self.DOWNLOAD_DIR, self.CLIPS_DIR, self.LOGOS_DIR]:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Channel URLs - REAL CHANNELS
        self.YOUTUBE_CHANNELS = {
            'naturesmomentstv': 'https://www.youtube.com/@naturesmomentstv/videos',
            'navwildanimaldocumentary': 'https://www.youtube.com/@navwildanimaldocumentary/videos',
            'wildnatureus2024': 'https://www.youtube.com/@wildnatureus2024/videos',
            'ScenicScenes': 'https://www.youtube.com/@ScenicScenes/videos'
        }

        # Video limits
        self.MAX_VIDEOS_TOTAL = 4
        self.MIN_VIDEO_DURATION = 600  # 10 minutes
        self.MAX_VIDEO_DURATION = 18000  # 5 hours
        self.MAX_VIDEO_AGE_DAYS = 1500  # ~4 years
        
        print("✅ Config initialized successfully")
    
    def get_logo_path(self, channel: str) -> str:
        """Get the path to the logo for a given channel."""
        logo_path = Path(self.LOGOS_DIR) / f"{channel}.png"
        if not logo_path.exists():
            raise FileNotFoundError(f"Logo not found for channel: {channel} at {logo_path}")
        return str(logo_path)