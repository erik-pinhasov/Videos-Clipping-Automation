"""
YouTube API service for video discovery and management.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from src.core.logger import get_logger
from src.core.exceptions import YouTubeAPIError
import config


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
    
    def get_channel_videos(self, channel_name: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent videos from a channel.
        
        Args:
            channel_name: Channel name or ID
            max_results: Maximum number of videos to return
            
        Returns:
            List of video dictionaries
        """
        try:
            self._check_rate_limits()
            
            self.logger.info(f"Fetching videos from channel: {channel_name}")
            
            # Use real API if available, otherwise mock data
            if self.youtube_service:
                try:
                    videos = self._fetch_real_channel_videos(channel_name, max_results)
                    if videos:
                        self._api_calls_count += 1
                        self.logger.info(f"✓ Fetched {len(videos)} videos from YouTube API")
                        return videos
                except Exception as e:
                    self.logger.warning(f"Real API call failed: {e}, falling back to mock data")
            
            # Fallback to mock data
            mock_videos = self._generate_mock_videos(channel_name, max_results)
            self._api_calls_count += 1
            self.logger.info(f"✓ Generated {len(mock_videos)} mock videos")
            return mock_videos
            
        except Exception as e:
            self.logger.error(f"Error fetching channel videos: {e}")
            raise YouTubeAPIError(f"Failed to fetch videos from {channel_name}: {e}")
    
    def _fetch_real_channel_videos(self, channel_name: str, max_results: int) -> List[Dict[str, Any]]:
        """Fetch videos using real YouTube Data API."""
        try:
            # First, get channel ID from channel name
            search_response = self.youtube_service.search().list(
                q=channel_name,
                type='channel',
                part='id,snippet',
                maxResults=1
            ).execute()
            
            if not search_response.get('items'):
                self.logger.warning(f"Channel not found: {channel_name}")
                return []
            
            channel_id = search_response['items'][0]['id']['channelId']
            
            # Get videos from the channel
            search_response = self.youtube_service.search().list(
                channelId=channel_id,
                type='video',
                part='id,snippet',
                order='date',
                maxResults=max_results
            ).execute()
            
            videos = []
            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                
                # Get additional video details
                video_response = self.youtube_service.videos().list(
                    part='contentDetails,statistics',
                    id=video_id
                ).execute()
                
                video_details = video_response['items'][0] if video_response['items'] else {}
                
                # Parse duration
                duration_str = video_details.get('contentDetails', {}).get('duration', 'PT0S')
                duration = self._parse_duration(duration_str)
                
                videos.append({
                    'id': video_id,
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'url': f"https://youtube.com/watch?v={video_id}",
                    'duration': duration,
                    'upload_date': item['snippet']['publishedAt'][:10],
                    'view_count': int(video_details.get('statistics', {}).get('viewCount', 0)),
                    'channel': channel_name
                })
            
            return videos
            
        except Exception as e:
            self.logger.error(f"Real API fetch failed: {e}")
            return []
    
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
    
    def _generate_mock_videos(self, channel_name: str, max_results: int) -> List[Dict[str, Any]]:
        """Generate mock video data for testing/development."""
        mock_videos = []
        
        # Get content category for this channel
        category = self.config.get_channel_category(channel_name)
        
        for i in range(max_results):
            video_id = f"mock_{channel_name}_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Vary upload dates (recent videos)
            days_ago = i + 1
            upload_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            # Vary durations within reasonable range
            duration = 120 + (i * 30)  # 2-8 minutes range
            
            mock_videos.append({
                "id": video_id,
                "title": f"Amazing {category.title()} Video {i+1} from {channel_name}",
                "description": f"Incredible {category} content from {channel_name}. Perfect for creating engaging shorts!",
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
            
            if self.youtube_service:
                try:
                    response = self.youtube_service.videos().list(
                        part='snippet,contentDetails,statistics',
                        id=video_id
                    ).execute()
                    
                    if response['items']:
                        item = response['items'][0]
                        duration = self._parse_duration(
                            item['contentDetails']['duration']
                        )
                        
                        return {
                            "id": video_id,
                            "title": item['snippet']['title'],
                            "description": item['snippet']['description'],
                            "duration": duration,
                            "upload_date": item['snippet']['publishedAt'][:10],
                            "tags": item['snippet'].get('tags', []),
                            "view_count": int(item['statistics'].get('viewCount', 0))
                        }
                        
                except Exception as e:
                    self.logger.warning(f"Real API call failed: {e}")
            
            # Fallback mock data
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