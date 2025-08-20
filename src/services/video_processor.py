import time
import signal
from pathlib import Path
from typing import List, Dict, Any
from src.core.exceptions import VideoProcessingError

import config
from src.core.logger import get_logger
from src.services.content_manager import ContentManager
import yt_dlp
import subprocess


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
    
    def download_video(self, video_url: str, output_path: str) -> str:
        """Download video using yt-dlp."""
        try:
            ydl_opts = {
                'outtmpl': f"{output_path}/%(id)s.%(ext)s",
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            raise VideoProcessingError(f"Failed to download video: {e}")
    
    def create_clips(self, video_path: str, clips_dir: str) -> List[str]:
        """Create short clips using ffmpeg."""
        # Example: Split video into 3 clips of 30 seconds each
        clips = []
        try:
            for i in range(3):
                clip_path = f"{clips_dir}/{Path(video_path).stem}_clip{i + 1}.mp4"
                start_time = i * 30
                subprocess.run([
                    "ffmpeg", "-i", video_path, "-ss", str(start_time), "-t", "30",
                    "-c:v", "libx264", "-c:a", "aac", clip_path
                ], check=True)
                clips.append(clip_path)
            return clips
        except Exception as e:
            raise VideoProcessingError(f"Failed to create clips: {e}")