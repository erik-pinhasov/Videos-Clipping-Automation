"""
Super simple config - no external dependencies.
"""

import os
from pathlib import Path


class Config:
    """Simple configuration."""
    
    def __init__(self):
        # Basic settings
        self.BASE_DIR = Path(__file__).parent
        self.DOWNLOAD_DIR = "media/downloads"
        self.CLIPS_DIR = "media/clips" 
        self.LOGOS_DIR = "media/logos"
        
        # Create directories
        for directory in [self.DOWNLOAD_DIR, self.CLIPS_DIR, self.LOGOS_DIR]:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        self.YOUTUBE_CHANNELS = [
            "naturesmomentstv",
            "navwildanimaldocumentary",
            "wildnatureus2024",
            "ScenicScenes"
        ]

        # Video limits
        self.MAX_VIDEOS_TOTAL = 10
        self.MIN_VIDEO_DURATION = 1800  # 5 minutes
        self.MAX_VIDEO_DURATION = 18000  # 1 hour
        self.MAX_VIDEO_AGE_DAYS = 1500
        
        print("✅ Config initialized successfully")