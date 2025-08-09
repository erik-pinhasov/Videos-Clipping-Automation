"""
YouTube API service for video discovery and management.
"""

from typing import Dict, Any, List, Optional
import re
from datetime import datetime, timedelta

from src.core.logger import get_logger
from src.core.exceptions import PipelineError
import config


class YouTubeAPI:
    """YouTube API wrapper for video operations."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        self._api_calls_count = 0
        self._last_reset_time = datetime.now()
    
    def get_channel_videos(self, channel_name: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent videos from a channel.
        
        For now, this returns mock data. In a real implementation,
        this would use the YouTube Data API v3.
        """
        try:
            self._check_rate_limits()
            
            self.logger.info(f"Fetching videos from channel: {channel_name}")
            
            # Mock data for development - replace with actual YouTube API calls
            mock_videos = self._generate_mock_videos(channel_name, max_results)
            
            self._api_calls_count += 1
            self.logger.debug(f"API calls made today: {self._api_calls_count}")
            
            return mock_videos
            
        except Exception as e:
            self.logger.error(f"Error fetching channel videos: {e}")
            raise PipelineError(f"Failed to fetch videos from {channel_name}: {e}")
    
    def _check_rate_limits(self) -> None:
        """Check and enforce API rate limits."""
        now = datetime.now()
        
        # Reset counter daily
        if (now - self._last_reset_time).days >= 1:
            self._api_calls_count = 0
            self._last_reset_time = now
        
        # YouTube API has 10,000 units per day quota by default
        max_calls = getattr(self.config, 'YOUTUBE_API_DAILY_QUOTA', 1000)
        if self._api_calls_count >= max_calls:
            raise PipelineError("YouTube API daily quota exceeded")
    
    def _generate_mock_videos(self, channel_name: str, max_results: int) -> List[Dict[str, Any]]:
        """Generate mock video data for testing."""
        mock_videos = []
        
        for i in range(max_results):
            video_id = f"mock_{channel_name}_{i}_{datetime.now().strftime('%Y%m%d')}"
            
            # Vary upload dates
            days_ago = i + 1
            upload_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            # Vary durations (60 to 600 seconds)
            duration = 60 + (i * 54)  # Spread across the range
            
            mock_videos.append({
                "id": video_id,
                "title": f"Amazing Wildlife Video {i+1} from {channel_name}",
                "description": f"Stunning nature footage from {channel_name}",
                "url": f"https://youtube.com/watch?v={video_id}",
                "duration": duration,
                "upload_date": upload_date,
                "view_count": 1000 + (i * 500),
                "channel": channel_name
            })
        
        return mock_videos
    
    def get_video_details(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific video."""
        try:
            self._check_rate_limits()
            
            # Mock implementation - replace with actual API call
            self.logger.debug(f"Fetching details for video: {video_id}")
            
            # Return mock data
            return {
                "id": video_id,
                "title": f"Video {video_id}",
                "description": "Mock video description",
                "duration": 300,
                "upload_date": datetime.now().strftime('%Y-%m-%d'),
                "tags": ["nature", "wildlife", "animals"]
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching video details: {e}")
            return None
    
    def search_videos(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for videos by query."""
        try:
            self._check_rate_limits()
            
            self.logger.info(f"Searching videos for: {query}")
            
            # Mock search results
            results = []
            for i in range(max_results):
                video_id = f"search_{query}_{i}"
                results.append({
                    "id": video_id,
                    "title": f"{query} - Search Result {i+1}",
                    "description": f"Search result for {query}",
                    "url": f"https://youtube.com/watch?v={video_id}",
                    "duration": 180 + (i * 30),
                    "upload_date": datetime.now().strftime('%Y-%m-%d')
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error searching videos: {e}")
            return []