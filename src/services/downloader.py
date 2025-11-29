import os
import yt_dlp
import config
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from src.core.logger import get_logger
from src.core.exceptions import DownloadError


class VideoDownloader:
    """Downloads videos from YouTube in highest available quality."""

    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)

        # Simplified quality preference: MP4 > Best
        self.quality_formats = [
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',  # Best MP4
            'bestvideo+bestaudio/best',                  # Best available
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
                'noplaylist': True,
                'quiet': False,
                'no_warnings': True,
            }

            self.logger.info(f"Downloading video: {video_url}")
            self.logger.info(f"Target quality: Best available with MP4 preference")

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
                raise ValueError("Invalid YouTube URL format")
        except Exception as e:
            self.logger.error(f"Failed to extract video ID: {e}")
            raise

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

        self.logger.error(f"No downloaded file found for video ID: {video_id}")
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

            self.logger.warning(f"Could not determine resolution for {video_path}. Falling back to 1920x1080.")
            return (1920, 1080)

        except Exception as e:
            self.logger.debug(f"Could not get video resolution: {e}")
            return (1920, 1080)