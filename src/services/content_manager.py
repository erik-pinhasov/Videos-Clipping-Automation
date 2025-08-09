"""
Content management service for tracking and retrieving videos.
"""

import json
import os
from typing import Dict, Any, List, Set, Optional
from pathlib import Path
from datetime import datetime, timedelta

from src.core.logger import get_logger
from src.core.exceptions import PipelineError
from src.services.youtube_api import YouTubeAPI
import config


class ContentManager:
    """Manages video content discovery and processing tracking."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        self.youtube_api = YouTubeAPI(cfg)
        self.used_videos_file = "used_videos.json"  # Keep in root as per your structure
        self._rate_limit_delay = 1.0  # Seconds between API calls
    
    def get_new_videos(self) -> List[Dict[str, Any]]:
        """Get new videos from configured channels."""
        try:
            used_videos = self._load_used_videos()
            all_videos = []
            
            channels = list(self.config.CHANNEL_LOGOS.keys())
            if not channels:
                self.logger.warning("No channels configured in CHANNEL_LOGOS")
                return []
            
            for channel in channels:
                self.logger.info(f"Fetching videos from channel: {channel}")
                
                try:
                    videos = self.youtube_api.get_channel_videos(
                        channel, 
                        max_results=getattr(self.config, 'MAX_VIDEOS_PER_CHANNEL', 10)
                    )
                    
                    # Filter out used videos and unsuitable videos
                    new_videos = []
                    for video in videos:
                        if self._is_video_suitable(video, used_videos):
                            new_videos.append(video)
                    
                    all_videos.extend(new_videos)
                    self.logger.info(f"Found {len(new_videos)} new videos from {channel}")
                    
                    # Rate limiting
                    import time
                    time.sleep(self._rate_limit_delay)
                    
                except Exception as e:
                    self.logger.error(f"Error fetching from channel {channel}: {e}")
                    continue
            
            # Sort by upload date (newest first)
            all_videos.sort(
                key=lambda x: x.get('upload_date', ''), 
                reverse=True
            )
            
            max_total = getattr(self.config, 'MAX_VIDEOS_TOTAL', 50)
            return all_videos[:max_total]
            
        except Exception as e:
            self.logger.error(f"Error getting new videos: {e}")
            return []
    
    def _is_video_suitable(self, video: Dict[str, Any], used_videos: Set[str]) -> bool:
        """Check if video is suitable for processing."""
        video_id = video["id"]
        
        # Skip if already used
        if video_id in used_videos:
            return False
        
        # Check duration
        duration = video.get("duration", 0)
        min_duration = getattr(self.config, 'MIN_VIDEO_DURATION', 60)
        max_duration = getattr(self.config, 'MAX_VIDEO_DURATION', 600)
        
        if duration < min_duration or duration > max_duration:
            self.logger.debug(f"Skipping {video_id}: duration {duration}s not in range ({min_duration}-{max_duration}s)")
            return False
        
        # Check upload date
        upload_date = video.get("upload_date")
        if upload_date:
            try:
                upload_dt = datetime.strptime(upload_date, "%Y-%m-%d")
                days_old = (datetime.now() - upload_dt).days
                max_age = getattr(self.config, 'MAX_VIDEO_AGE_DAYS', 30)
                if days_old > max_age:
                    self.logger.debug(f"Skipping {video_id}: {days_old} days old (max {max_age})")
                    return False
            except ValueError:
                self.logger.warning(f"Invalid upload date format for {video_id}: {upload_date}")
        
        return True
    
    def _load_used_videos(self) -> Set[str]:
        """Load list of already processed video IDs."""
        try:
            if os.path.exists(self.used_videos_file):
                with open(self.used_videos_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # Legacy format - just a list of IDs
                        return set(data)
                    return set(data.get('used_videos', []))
            return set()
        except Exception as e:
            self.logger.error(f"Error loading used videos: {e}")
            return set()
    
    def mark_video_used(self, video_id: str) -> None:
        """Mark a video as processed."""
        try:
            used_videos = self._load_used_videos()
            used_videos.add(video_id)
            
            data = {
                'used_videos': list(used_videos),
                'last_updated': datetime.now().isoformat(),
                'total_processed': len(used_videos)
            }
            
            with open(self.used_videos_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Marked video {video_id} as used (total processed: {len(used_videos)})")
            
        except Exception as e:
            self.logger.error(f"Error marking video as used: {e}")
    
    def is_video_processed(self, video_id: str) -> bool:
        """Check if video has been processed."""
        used_videos = self._load_used_videos()
        return video_id in used_videos
    
    def cleanup_old_entries(self, days_to_keep: int = 90) -> None:
        """Clean up old entries from used videos (optional maintenance)."""
        try:
            # This could be implemented to remove very old entries if needed
            # For now, we'll keep all entries as they're lightweight
            pass
        except Exception as e:
            self.logger.error(f"Error cleaning up old entries: {e}")