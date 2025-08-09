"""
Configuration settings for YouTube Shorts Automation Pipeline.
"""

import os
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for the automation pipeline."""
    
    # API Keys and Credentials (from .env)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    RUMBLE_EMAIL = os.getenv("RUMBLE_EMAIL")
    RUMBLE_PASSWORD = os.getenv("RUMBLE_PASSWORD")
    HF_API_TOKEN = os.getenv("HF_API_TOKEN")
    
    # File Paths
    YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "credentials.json")
    YOUTUBE_TOKEN_FILE = "credentials/youtube_token.json"
    
    # Directory Paths
    DOWNLOAD_DIR = "media/downloads"
    CLIPS_DIR = "media/clips"  
    AUDIO_DIR = "media/audio"
    ASSETS_DIR = "media/assets"
    LOGS_DIR = "logs"
    
    # Content Categories (customize for your niche)
    CONTENT_CATEGORIES = [
        "nature",
        "wildlife", 
        "animals",
        "documentary",
        "educational",
        "scenic",
        "relaxing"
    ]
    
    # Default metadata templates (customize for your content type)
    DEFAULT_TITLE_TEMPLATES = [
        "Amazing {category} Video",
        "Incredible {category} Moments", 
        "Beautiful {category} Scenes",
        "Stunning {category} Footage"
    ]
    
    DEFAULT_DESCRIPTION_TEMPLATE = """
Enjoy this amazing {category} content! 

🎬 Follow for more incredible videos
📱 Subscribe for daily {category} content
💝 Like if you enjoyed this video

#shorts #{category} #amazing #incredible #beautiful #nature #wildlife
    """.strip()
    
    # Default tags for content (customize for your niche)
    DEFAULT_TAGS = [
        "shorts",
        "amazing",
        "incredible", 
        "beautiful",
        "stunning",
        "viral",
        "trending"
    ]
    
    # Channel Configuration
    CHANNEL_LOGOS = {
        'naturesmomentstv': {
            'logo_path': 'media/assets/logo_naturesmomentstv.png',
            'location': 'top_left',
            'spacing_x': 17,
            'spacing_y': 15,
            'primary_category': 'nature',
            'content_tags': ['nature', 'wildlife', 'animals', 'documentary']
        },
        'navwildanimaldocumentary': {
            'logo_path': 'media/assets/navwildanimaldocumentary.png', 
            'location': 'top_right',
            'spacing_x': 14,
            'spacing_y': 44,
            'primary_category': 'wildlife',
            'content_tags': ['wildlife', 'animals', 'nature', 'documentary']
        },
        'wildnatureus2024': {
            'logo_path': 'media/assets/wildnatureus2024.png',
            'location': 'top_right', 
            'spacing_x': 189,
            'spacing_y': 107,
            'primary_category': 'nature',
            'content_tags': ['nature', 'wildlife', 'scenic', 'relaxing']
        },
        'ScenicScenes': {
            'logo_path': 'media/assets/ScenicScenes.png',
            'location': 'bottom_right',
            'spacing_x': 5,
            'spacing_y': 7,
            'primary_category': 'scenic',
            'content_tags': ['scenic', 'nature', 'relaxing', 'beautiful']
        }
    }
    
    # Video Processing Settings
    MIN_VIDEO_DURATION = 60      # seconds
    MAX_VIDEO_DURATION = 600     # seconds (10 minutes)
    MAX_VIDEO_AGE_DAYS = 30      # days
    MAX_VIDEOS_PER_CHANNEL = 5   # per fetch
    MAX_VIDEOS_TOTAL = 20        # total to process per run
    
    # Clip Settings
    CLIP_DURATION_MIN = 15       # seconds
    CLIP_DURATION_MAX = 60       # seconds
    MAX_CLIPS_PER_VIDEO = 3      # maximum clips to create
    
    # API Rate Limits
    YOUTUBE_API_DAILY_QUOTA = 1000
    OPENAI_API_DAILY_QUOTA = 1000
    MAX_DAILY_UPLOADS = 50
    
    # Upload Settings
    RUMBLE_UPLOAD_TIMEOUT = 600  # seconds (10 minutes)
    YOUTUBE_UPLOAD_TIMEOUT = 600 # seconds (10 minutes)
    UPLOAD_RATE_LIMIT_DELAY = 5  # seconds between uploads
    
    # Quality Settings
    VIDEO_QUALITY = "720p"
    AUDIO_BITRATE = "128k"
    
    # Processing Settings
    MAX_CONCURRENT_UPLOADS = 2
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 5              # seconds
    
    # Content Generation Settings
    USE_AI_METADATA = True
    METADATA_LANGUAGE = "en"
    MAX_TITLE_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 5000
    
    def get_channel_category(self, channel: str) -> str:
        """Get primary category for a channel."""
        channel_config = self.CHANNEL_LOGOS.get(channel, {})
        return channel_config.get('primary_category', 'content')
    
    def get_channel_tags(self, channel: str) -> List[str]:
        """Get content tags for a channel."""
        channel_config = self.CHANNEL_LOGOS.get(channel, {})
        channel_tags = channel_config.get('content_tags', [])
        return list(set(channel_tags + self.DEFAULT_TAGS))
    
    def get_fallback_metadata(self, channel: str, title: str = None) -> Dict[str, Any]:
        """Get fallback metadata when AI generation fails."""
        category = self.get_channel_category(channel)
        tags = self.get_channel_tags(channel)
        
        # Generate fallback title
        if not title:
            import random
            template = random.choice(self.DEFAULT_TITLE_TEMPLATES)
            title = template.format(category=category.title())
        
        # Generate fallback description
        description = self.DEFAULT_DESCRIPTION_TEMPLATE.format(category=category)
        
        return {
            "title": title[:self.MAX_TITLE_LENGTH],
            "description": description[:self.MAX_DESCRIPTION_LENGTH],
            "tags": tags
        }
    
    def validate(self) -> bool:
        """Validate configuration settings."""
        required_settings = [
            'OPENAI_API_KEY',
            'YOUTUBE_API_KEY'
        ]
        
        missing = []
        for setting in required_settings:
            if not getattr(self, setting):
                missing.append(setting)
        
        if missing:
            print(f"Missing required configuration: {', '.join(missing)}")
            return False
        
        # Validate channel logos exist
        for channel, config_dict in self.CHANNEL_LOGOS.items():
            logo_path = config_dict.get('logo_path')
            if logo_path and not os.path.exists(logo_path):
                print(f"Warning: Logo file not found for channel {channel}: {logo_path}")
        
        return True


# Global constants (backwards compatibility)
DOWNLOAD_DIR = Config.DOWNLOAD_DIR
CLIPS_DIR = Config.CLIPS_DIR
AUDIO_DIR = Config.AUDIO_DIR
ASSETS_DIR = Config.ASSETS_DIR

# Channel logos for backwards compatibility
CHANNEL_LOGOS = Config.CHANNEL_LOGOS