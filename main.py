#!/usr/bin/env python3
# filepath: c:\Users\erikp\Desktop\vscode\youtube_short_automation\main.py
"""
YouTube Shorts Automation Pipeline

Automatically processes videos from configured channels:
- Downloads videos from specified channels
- Adds channel logo overlay
- Uploads full video to Rumble with AI-generated metadata
- Creates highlight clips for YouTube Shorts
- Uploads shorts to YouTube with optimized metadata
- Cleans up temporary files and marks videos as processed
"""

import sys
import time
import signal
from pathlib import Path
from typing import Dict, Any

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Project imports
import config
from src.core.logger import setup_logging, get_logger
from src.core.exceptions import PipelineError, VideoProcessingError
from src.services.video_processor import VideoProcessor
from src.services.content_manager import ContentManager
from src.utils.cleanup import ResourceCleaner


class AutomationPipeline:
    """Main automation pipeline orchestrator."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = config.Config()
        self.video_processor = VideoProcessor(self.config)
        self.content_manager = ContentManager(self.config)
        self.resource_cleaner = ResourceCleaner()
        self.shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info("🛑 Shutdown signal received, finishing current video...")
        self.shutdown_requested = True
    
    def _setup_directories(self) -> None:
        """Create required directories."""
        directories = [
            self.config.DOWNLOAD_DIR,
            self.config.CLIPS_DIR,
            self.config.ASSETS_DIR,
            "logs",
            "data",
            "credentials"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _process_single_video(self, video_info: Dict[str, Any], channel: str) -> bool:
        """Process a single video through the complete pipeline."""
        video_id = video_info["id"]
        title = video_info.get("title", "Unknown")
        
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info(f"🎬 PROCESSING VIDEO: {title}")
        self.logger.info(f"📋 Video ID: {video_id}")
        self.logger.info(f"📺 Channel: {channel}")
        self.logger.info("=" * 80)
        
        try:
            result = self.video_processor.process_video(video_info, channel)
            
            if result.success:
                # Mark as processed and cleanup
                self.content_manager.mark_video_used(video_id)
                self.resource_cleaner.cleanup_video_files(video_id)
                
                self.logger.info("")
                self.logger.info("🎉 VIDEO PROCESSING COMPLETED SUCCESSFULLY!")
                self.logger.info(f"📊 Summary:")
                self.logger.info(f"   • Clips created: {result.clips_created}")
                self.logger.info(f"   • YouTube uploads: {result.youtube_uploads}")
                self.logger.info(f"   • Rumble upload: {'✅' if result.rumble_uploaded else '❌'}")
                self.logger.info(f"   • Processing time: {result.processing_time:.1f}s")
                self.logger.info("=" * 80)
                return True
            else:
                self.logger.error("")
                self.logger.error("💥 VIDEO PROCESSING FAILED!")
                self.logger.error(f"❌ Error: {result.error}")
                self.logger.error("🛑 PIPELINE STOPPED - Manual intervention required")
                self.logger.error("=" * 80)
                return False
                
        except VideoProcessingError as e:
            self.logger.error(f"💥 Video processing failed for {video_id}: {e}")
            self.logger.error("🛑 PIPELINE STOPPED")
            return False
        except Exception as e:
            self.logger.error(f"💥 Unexpected error processing {video_id}: {e}", exc_info=True)
            self.logger.error("🛑 PIPELINE STOPPED")
            return False
    
    def run(self) -> None:
        """Run the main automation loop."""
        self.logger.info("🚀 YouTube Shorts Automation Pipeline Starting...")
        self.logger.info(f"📁 Working Directory: {Path.cwd()}")
        
        try:
            # Setup
            self._setup_directories()
            
            if not self.video_processor.initialize():
                self.logger.error("💥 Failed to initialize video processor")
                return
            
            # Get channels from configuration
            channels = list(self.config.CHANNEL_LOGOS.keys())
            if not channels:
                self.logger.error("💥 No channels configured in CHANNEL_LOGOS")
                self.logger.error("Please configure channels in config.py")
                return
            
            self.logger.info(f"📺 Configured channels: {', '.join(channels)}")
            self.logger.info(f"⚙️ Video duration range: {self.config.MIN_VIDEO_DURATION}s - {self.config.MAX_VIDEO_DURATION}s")
            self.logger.info(f"📊 Max videos per run: {self.config.MAX_VIDEOS_TOTAL}")
            
            # Cleanup old files before starting
            self.logger.info("🧹 Cleaning up old files...")
            self.resource_cleaner.cleanup_old_files(24)  # Remove files older than 24 hours
            
            # Main processing loop
            while not self.shutdown_requested:
                try:
                    self.logger.info("")
                    self.logger.info("🔍 Searching for new videos to process...")
                    
                    videos = self.content_manager.get_new_videos()
                    
                    if not videos:
                        self.logger.info("😴 No new videos found")
                        self.logger.info("⏰ Waiting 1 hour before next check...")
                        self._wait_with_interrupt_check(3600)
                        continue
                    
                    self.logger.info(f"🎯 Found {len(videos)} new videos to process!")
                    
                    # Process each video
                    for i, video_info in enumerate(videos):
                        if self.shutdown_requested:
                            self.logger.info("🛑 Shutdown requested, stopping...")
                            break
                        
                        video_id = video_info["id"]
                        
                        # Skip if already processed
                        if self.content_manager.is_video_processed(video_id):
                            self.logger.info(f"⏭️ Skipping {video_id}: already processed")
                            continue
                        
                        # Select channel (round-robin)
                        channel = channels[i % len(channels)]
                        
                        # Process the video
                        success = self._process_single_video(video_info, channel)
                        
                        if not success:
                            self.logger.error("🚨 Processing failed - stopping pipeline")
                            return
                        
                        # Brief pause between videos
                        if not self.shutdown_requested and i < len(videos) - 1:
                            self.logger.info("⏸️ Brief pause before next video...")
                            self._wait_with_interrupt_check(10)
                    
                    if not self.shutdown_requested:
                        self.logger.info("")
                        self.logger.info("✅ All videos processed successfully!")
                        self.logger.info("⏰ Waiting 1 hour before next check...")
                        self._wait_with_interrupt_check(3600)
                    
                except KeyboardInterrupt:
                    self.logger.info("⌨️ Keyboard interrupt received")
                    break
                except Exception as e:
                    self.logger.error(f"💥 Error in main loop: {e}", exc_info=True)
                    self.logger.info("🔄 Retrying in 5 minutes...")
                    self._wait_with_interrupt_check(300)
            
        except Exception as e:
            self.logger.error(f"💥 Fatal error in pipeline: {e}", exc_info=True)
        finally:
            self.logger.info("")
            self.logger.info("🛑 YouTube Shorts Automation Pipeline Stopped")
            self.logger.info("👋 Goodbye!")
    
    def _wait_with_interrupt_check(self, seconds: int) -> None:
        """Wait for specified seconds while checking for shutdown signal."""
        start_time = time.time()
        while time.time() - start_time < seconds and not self.shutdown_requested:
            time.sleep(1)


def main():
    """Main entry point."""
    try:
        # Setup logging first
        setup_logging()
        logger = get_logger(__name__)
        
        logger.info("🎬 Initializing YouTube Shorts Automation Pipeline...")
        
        # Create and run pipeline
        pipeline = AutomationPipeline()
        pipeline.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()