"""
High-quality video downloader with 4K support and adaptive quality fallback.
"""

import os
import yt_dlp
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import config
from src.core.logger import get_logger
from src.core.exceptions import DownloadError


class VideoDownloader:
    """Downloads videos in highest available quality with 4K preference."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Quality preference: 4K > 1440p > 1080p > 720p
        self.quality_formats = [
            'best[height>=2160][ext=mp4]',  # 4K MP4
            'best[height>=2160]',           # 4K any format
            'best[height>=1440][ext=mp4]',  # 1440p MP4
            'best[height>=1440]',           # 1440p any format
            'best[height>=1080][ext=mp4]',  # 1080p MP4
            'best[height>=1080]',           # 1080p any format
            'best[ext=mp4]',                # Best MP4
            'best'                          # Fallback to any best
        ]
        
    def download(self, video_url: str, video_id: str = None) -> str:
        """Download video in highest quality available."""
        try:
            # Extract video ID if not provided
            if not video_id:
                video_id = self._extract_video_id(video_url)
            
            # Ensure download directory exists
            Path(self.config.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
            
            # Set up yt-dlp options for quality download
            output_template = os.path.join(self.config.DOWNLOAD_DIR, f'{video_id}.%(ext)s')
            
            ydl_opts = {
                'format': '/'.join(self.quality_formats),
                'outtmpl': output_template,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'noplaylist': True,
                'extract_flat': False,
                'quiet': False,
                'no_warnings': False,
            }
            
            self.logger.info(f"Downloading video: {video_url}")
            self.logger.info(f"Target quality: 4K (3840x2160) with fallback")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info first to check available quality
                info = ydl.extract_info(video_url, download=False)
                self._log_available_quality(info)
                
                # Download the video
                ydl.download([video_url])
                
                # Find and return the downloaded file
                downloaded_file = self._find_downloaded_file(video_id)
                
                if downloaded_file:
                    # Log final download info
                    file_size = os.path.getsize(downloaded_file) / (1024 * 1024)
                    resolution = self._get_video_resolution(downloaded_file)
                    
                    self.logger.info(f"✓ Downloaded: {Path(downloaded_file).name}")
                    self.logger.info(f"  Resolution: {resolution[0]}x{resolution[1]}")
                    self.logger.info(f"  File size: {file_size:.1f} MB")
                    
                    return downloaded_file
                else:
                    raise DownloadError(f"Downloaded file not found for video ID: {video_id}")
                    
        except Exception as e:
            self.logger.error(f"Download failed for {video_url}: {e}")
            raise DownloadError(f"Failed to download video: {e}")
    
    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from YouTube URL."""
        try:
            if 'youtube.com/watch?v=' in video_url:
                return video_url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in video_url:
                return video_url.split('youtu.be/')[1].split('?')[0]
            else:
                # Generate a safe filename from URL
                import hashlib
                return hashlib.md5(video_url.encode()).hexdigest()[:12]
        except Exception:
            import time
            return f"video_{int(time.time())}"
    
    def _log_available_quality(self, info: Dict[str, Any]) -> None:
        """Log available video qualities."""
        try:
            formats = info.get('formats', [])
            if not formats:
                return
                
            # Find unique resolutions
            resolutions = set()
            for fmt in formats:
                if fmt.get('height') and fmt.get('width'):
                    resolutions.add(f"{fmt['width']}x{fmt['height']}")
            
            if resolutions:
                sorted_res = sorted(resolutions, key=lambda x: int(x.split('x')[1]), reverse=True)
                self.logger.info(f"  Available qualities: {', '.join(sorted_res)}")
                
        except Exception as e:
            self.logger.debug(f"Could not log available qualities: {e}")
    
    def _find_downloaded_file(self, video_id: str) -> Optional[str]:
        """Find the downloaded file by video ID."""
        download_dir = Path(self.config.DOWNLOAD_DIR)
        
        # Common video extensions
        extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov']
        
        for ext in extensions:
            file_path = download_dir / f"{video_id}{ext}"
            if file_path.exists():
                return str(file_path)
        
        # Fallback: search for any file starting with video_id
        for file_path in download_dir.glob(f"{video_id}.*"):
            if file_path.suffix.lower() in extensions:
                return str(file_path)
        
        return None
    
    def _get_video_resolution(self, video_path: str) -> Tuple[int, int]:
        """Get video resolution using ffmpeg."""
        try:
            import subprocess
            
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width', 0)
                        height = stream.get('height', 0)
                        if width and height:
                            return (width, height)
            
            # Fallback
            return (1920, 1080)
            
        except Exception as e:
            self.logger.debug(f"Could not get video resolution: {e}")
            return (1920, 1080)
    
    def get_video_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Get video information without downloading."""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'upload_date': info.get('upload_date'),
                    'uploader': info.get('uploader'),
                    'view_count': info.get('view_count'),
                    'width': info.get('width'),
                    'height': info.get('height')
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get video info for {video_url}: {e}")
            return None