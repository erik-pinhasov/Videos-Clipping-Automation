"""
Video downloader service using yt-dlp for downloading videos from various platforms.
"""

import os
import yt_dlp
from typing import Dict, Any, Optional
from pathlib import Path

from src.core.logger import get_logger
from src.core.exceptions import DownloadError
import config


class VideoDownloader:
    """Handles video downloads using yt-dlp."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # yt-dlp options
        self.ytdl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': os.path.join(self.config.DOWNLOAD_DIR, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extractaudio': False,
            'audioformat': 'mp3',
            'embed_subs': False,
        }
    
    def download(self, video_url: str, video_id: str = None) -> str:
        """
        Download video from URL.
        
        Args:
            video_url: URL of the video to download
            video_id: Optional video ID for filename
            
        Returns:
            str: Path to downloaded video file
        """
        try:
            self.logger.info(f"Downloading video: {video_url}")
            
            # Ensure download directory exists
            Path(self.config.DOWNLOAD_DIR).mkdir(exist_ok=True)
            
            # Update output template if specific video_id provided
            if video_id:
                self.ytdl_opts['outtmpl'] = os.path.join(
                    self.config.DOWNLOAD_DIR, f'{video_id}.%(ext)s'
                )
            
            with yt_dlp.YoutubeDL(self.ytdl_opts) as ydl:
                # Extract info to get actual filename
                info = ydl.extract_info(video_url, download=False)
                filename = ydl.prepare_filename(info)
                
                # Download the video
                ydl.download([video_url])
                
                if os.path.exists(filename):
                    self.logger.info(f"✓ Downloaded: {Path(filename).name}")
                    return filename
                else:
                    raise DownloadError(f"Downloaded file not found: {filename}")
                    
        except Exception as e:
            self.logger.error(f"Download failed for {video_url}: {e}")
            raise DownloadError(f"Failed to download video: {e}")
    
    def get_video_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get video information without downloading."""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'duration': info.get('duration'),
                    'upload_date': info.get('upload_date'),
                    'view_count': info.get('view_count'),
                    'uploader': info.get('uploader')
                }
        except Exception as e:
            self.logger.error(f"Failed to get video info: {e}")
            return None