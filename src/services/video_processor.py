import time
import signal
from pathlib import Path
from typing import List, Dict, Any
from src.core.exceptions import VideoProcessingError, DownloadError

import config
from src.core.logger import get_logger
from src.services.content_manager import ContentManager
from src.services.clip_creator import ClipCreator
from src.services.branding import VideoBranding
from src.services.highlight_detector import HighlightDetector
from src.services.metadata_service import MetadataService
import yt_dlp
import subprocess
import os


class VideoProcessor:
    """Simple video processor with graceful shutdown."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        self.should_stop = False
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialize content manager
        self.content_manager = ContentManager(cfg)
    
    def _signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        self.logger.info("🛑 Graceful shutdown requested...")
        self.should_stop = True
    
    def run_automation(self, max_videos: int = 5) -> Dict[str, Any]:
        """Run simple automation."""
        try:
            self.logger.info(f"🔍 Looking for {max_videos} videos to process...")
            
            # Get videos
            videos = self.content_manager.get_new_videos()
            if not videos:
                return {'success': True, 'message': 'No videos found'}
            
            # Limit videos
            videos = videos[:max_videos]
            
            self.logger.info(f"📹 Found {len(videos)} videos to process")
            
            # Process each video
            processed = 0
            for i, video in enumerate(videos):
                if self.should_stop:
                    self.logger.info("🛑 Stopping due to user request")
                    break
                
                self.logger.info(f"Processing video {i+1}/{len(videos)}: {video['title'][:50]}...")
                
                # Simulate processing (replace with actual processing)
                success = self._process_video(video)
                
                if success:
                    processed += 1
                    self.logger.info(f"✅ Video {i+1} completed")
                else:
                    self.logger.error(f"❌ Video {i+1} failed")
                
                # Check for stop signal
                if self.should_stop:
                    break
                
                # Brief pause
                time.sleep(2)
            
            return {
                'success': True,
                'processed': processed,
                'total': len(videos)
            }
            
        except Exception as e:
            self.logger.error(f"Automation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_video(self, video: Dict[str, Any]) -> bool:
        """Process single video (simplified for now)."""
        try:
            # For now, just log the video info
            self.logger.info(f"  Title: {video['title']}")
            self.logger.info(f"  Channel: {video['channel']}")
            self.logger.info(f"  Duration: {video.get('duration', 'Unknown')} seconds")
            
            # Simulate processing time
            time.sleep(3)
            
            # Check for stop during processing
            if self.should_stop:
                return False
            
            # Mark as used (only on success)
            self.content_manager.mark_video_used(video['url'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Video processing failed: {e}")
            return False
    
    def download_video(self, url: str) -> str:
        """Download the given YouTube video URL using yt-dlp."""
        try:
            self.logger.info(f"🔄 Downloading video: {url}")
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                'quiet': False,
                'cookiefile': 'cookies.txt',  # Use cookies for authentication
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                self.logger.info(f"✅ Successfully downloaded video: {info['title']}")
                return ydl.prepare_filename(info)
        except Exception as e:
            self.logger.error(f"❌ Failed to download video: {e}")
            raise DownloadError(f"Failed to download video: {e}")
    
    def create_clips(self, video_path: str, clips_dir: str, video_id: str, channel: str) -> List[str]:
        """Create short clips with viral-style subtitles."""
        try:
            # Initialize HighlightDetector
            highlight_detector = HighlightDetector(self.config)
            
            # Detect highlights
            highlights = highlight_detector.detect(video_path, channel)
            if not highlights:
                raise VideoProcessingError("No highlights detected in the video.")
            
            # Create clips from highlights
            clip_creator = ClipCreator(self.config)
            clips = clip_creator.create_clips(video_path, highlights, video_id, channel)
            return clips
        except Exception as e:
            raise VideoProcessingError(f"Failed to create clips: {e}")

    def _get_video_duration(self, video_path: str) -> int:
        """Get the duration of a video in seconds."""
        try:
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                capture_output=True, text=True
            )
            return int(float(result.stdout.strip()))
        except Exception as e:
            self.logger.error(f"Failed to get video duration: {e}")
            return 0

    def add_logo(self, video_path: str, output_dir: str, channel: str) -> str:
        """Add a logo overlay to the video."""
        try:
            branding = VideoBranding(self.config)
            output_path = os.path.join(output_dir, f"{Path(video_path).stem}_branded.mp4")
            return branding.add_logo(video_path, output_path, channel)
        except Exception as e:
            raise VideoProcessingError(f"Failed to add logo: {e}")

    def generate_metadata(self, video_path: str, channel: str) -> Dict[str, Any]:
        """Generate metadata for the video using OpenAI API."""
        try:
            from src.services.metadata_service import MetadataService
            metadata_service = MetadataService(self.config)
            title = Path(video_path).stem
            metadata = metadata_service.generate_metadata(title, channel)
            return metadata
        except Exception as e:
            raise VideoProcessingError(f"Failed to generate metadata: {e}")