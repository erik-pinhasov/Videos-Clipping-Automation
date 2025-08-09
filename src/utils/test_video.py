"""
Video testing utility for testing single video processing pipeline.
Supports both local video files and YouTube URLs for testing.
"""

import sys
import argparse
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.core.logger import setup_logging, get_logger
from src.core.exceptions import VideoProcessingError
from src.services.video_processor import VideoProcessor
from src.services.downloader import VideoDownloader
from src.utils.cleanup import ResourceCleaner


class VideoTester:
    """Test single video processing pipeline."""
    
    def __init__(self):
        self.config = config.Config()
        self.logger = get_logger(__name__)
        self.video_processor = VideoProcessor(self.config)
        self.downloader = VideoDownloader(self.config)
        self.resource_cleaner = ResourceCleaner()
    
    def test_from_file(self, video_path: str, channel: str, test_id: str = None) -> bool:
        """
        Test video processing pipeline using local video file.
        
        Args:
            video_path: Path to local video file
            channel: Channel name for branding (must be in config.CHANNEL_LOGOS)
            test_id: Optional test ID for file naming
            
        Returns:
            bool: True if test successful, False otherwise
        """
        try:
            if not Path(video_path).exists():
                self.logger.error(f"Video file not found: {video_path}")
                return False
            
            if channel not in self.config.CHANNEL_LOGOS:
                self.logger.error(f"Channel '{channel}' not found in configuration")
                self.logger.info(f"Available channels: {list(self.config.CHANNEL_LOGOS.keys())}")
                return False
            
            # Generate test video info
            if not test_id:
                test_id = f"test_{int(time.time())}"
            
            video_info = {
                "id": test_id,
                "title": f"Test Video - {Path(video_path).stem}",
                "description": f"Test video from file: {video_path}",
                "url": f"file://{video_path}",
                "duration": self._get_video_duration(video_path),
                "upload_date": time.strftime("%Y-%m-%d"),
                "channel": channel,
                "local_file": video_path  # Special flag for local files
            }
            
            self.logger.info(f"Testing video from file: {video_path}")
            self.logger.info(f"Channel: {channel}")
            self.logger.info(f"Test ID: {test_id}")
            
            return self._run_test(video_info, channel)
            
        except Exception as e:
            self.logger.error(f"Test from file failed: {e}", exc_info=True)
            return False
    
    def test_from_url(self, video_url: str, channel: str, test_id: str = None) -> bool:
        """
        Test video processing pipeline using YouTube URL.
        
        Args:
            video_url: YouTube video URL
            channel: Channel name for branding (must be in config.CHANNEL_LOGOS)
            test_id: Optional test ID for file naming
            
        Returns:
            bool: True if test successful, False otherwise
        """
        try:
            if channel not in self.config.CHANNEL_LOGOS:
                self.logger.error(f"Channel '{channel}' not found in configuration")
                self.logger.info(f"Available channels: {list(self.config.CHANNEL_LOGOS.keys())}")
                return False
            
            # Get video info from URL
            self.logger.info(f"Fetching video info from: {video_url}")
            video_info_raw = self.downloader.get_video_info(video_url)
            
            if not video_info_raw:
                self.logger.error("Failed to get video information from URL")
                return False
            
            # Generate test ID if not provided
            if not test_id:
                test_id = f"test_{video_info_raw.get('id', int(time.time()))}"
            
            # Format video info for our pipeline
            video_info = {
                "id": test_id,
                "title": video_info_raw.get('title', 'Test Video'),
                "description": video_info_raw.get('description', 'Test video from URL'),
                "url": video_url,
                "duration": video_info_raw.get('duration', 0),
                "upload_date": video_info_raw.get('upload_date', time.strftime("%Y-%m-%d")),
                "channel": channel,
                "original_id": video_info_raw.get('id')
            }
            
            self.logger.info(f"Testing video: {video_info['title']}")
            self.logger.info(f"Duration: {video_info['duration']} seconds")
            self.logger.info(f"Channel: {channel}")
            self.logger.info(f"Test ID: {test_id}")
            
            return self._run_test(video_info, channel)
            
        except Exception as e:
            self.logger.error(f"Test from URL failed: {e}", exc_info=True)
            return False
    
    def _run_test(self, video_info: Dict[str, Any], channel: str) -> bool:
        """Run the complete test pipeline."""
        try:
            # Initialize services
            if not self.video_processor.initialize():
                self.logger.error("Failed to initialize video processor")
                return False
            
            self.logger.info("=" * 60)
            self.logger.info("🧪 STARTING VIDEO PROCESSING TEST")
            self.logger.info("=" * 60)
            
            start_time = time.time()
            
            # Run the processing pipeline
            result = self.video_processor.process_video(video_info, channel)
            
            processing_time = time.time() - start_time
            
            if result.success:
                self.logger.info("=" * 60)
                self.logger.info("✅ TEST COMPLETED SUCCESSFULLY!")
                self.logger.info(f"📊 Results:")
                self.logger.info(f"   • Processing time: {processing_time:.1f}s")
                self.logger.info(f"   • Clips created: {result.clips_created}")
                self.logger.info(f"   • Uploads successful: {result.uploads_successful}")
                self.logger.info("=" * 60)
                
                # Cleanup test files after successful test
                self.logger.info("🧹 Cleaning up test files...")
                self.resource_cleaner.cleanup_video_files(video_info["id"])
                
                return True
            else:
                self.logger.error("=" * 60)
                self.logger.error("❌ TEST FAILED!")
                self.logger.error(f"Error: {result.error}")
                self.logger.error("=" * 60)
                return False
                
        except Exception as e:
            self.logger.error(f"Test execution failed: {e}", exc_info=True)
            return False
    
    def _get_video_duration(self, video_path: str) -> int:
        """Get video duration using ffprobe."""
        try:
            import subprocess
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return int(float(result.stdout.strip()))
            else:
                self.logger.warning(f"Could not get duration for {video_path}")
                return 300  # Default 5 minutes
                
        except Exception as e:
            self.logger.warning(f"Duration detection failed: {e}")
            return 300
    
    def list_available_channels(self) -> None:
        """List all available channels from configuration."""
        channels = list(self.config.CHANNEL_LOGOS.keys())
        self.logger.info("Available channels for testing:")
        for i, channel in enumerate(channels, 1):
            logo_config = self.config.CHANNEL_LOGOS[channel]
            self.logger.info(f"  {i}. {channel}")
            self.logger.info(f"     Logo: {logo_config.get('logo_path', 'Not set')}")
            self.logger.info(f"     Location: {logo_config.get('location', 'Not set')}")


def main():
    """Main entry point for video testing."""
    parser = argparse.ArgumentParser(
        description="Test video processing pipeline with a single video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with local video file
  python src/utils/test_video.py --file "path/to/video.mp4" --channel "naturesmomentstv"
  
  # Test with YouTube URL
  python src/utils/test_video.py --url "https://youtube.com/watch?v=VIDEO_ID" --channel "ScenicScenes"
  
  # List available channels
  python src/utils/test_video.py --list-channels
  
  # Test with custom test ID
  python src/utils/test_video.py --file "test.mp4" --channel "naturesmomentstv" --test-id "my_test_1"
        """
    )
    
    parser.add_argument('--file', '-f', help='Path to local video file')
    parser.add_argument('--url', '-u', help='YouTube video URL')
    parser.add_argument('--channel', '-c', help='Channel name for branding')
    parser.add_argument('--test-id', help='Custom test ID for file naming')
    parser.add_argument('--list-channels', action='store_true', help='List available channels')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(log_level=args.log_level)
    logger = get_logger(__name__)
    
    try:
        tester = VideoTester()
        
        if args.list_channels:
            tester.list_available_channels()
            return
        
        if not args.file and not args.url:
            parser.print_help()
            logger.error("Either --file or --url must be specified")
            sys.exit(1)
        
        if args.file and args.url:
            logger.error("Cannot specify both --file and --url")
            sys.exit(1)
        
        if not args.channel:
            logger.error("--channel must be specified")
            tester.list_available_channels()
            sys.exit(1)
        
        # Run the test
        if args.file:
            success = tester.test_from_file(args.file, args.channel, args.test_id)
        else:
            success = tester.test_from_url(args.url, args.channel, args.test_id)
        
        if success:
            logger.info("🎉 Test completed successfully!")
            sys.exit(0)
        else:
            logger.error("💥 Test failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


'''
# Basic test
python src/utils/video_tester.py --file path/to/video.mp4

# Test with specific channel branding
python src/utils/video_tester.py --file video.mp4 --channel naturesmomentstv

# Debug mode with file preservation
python src/utils/video_tester.py --file video.mp4 --no-cleanup --log-level DEBUG

----------

# Test download and full pipeline
python src/utils/video_tester.py --url "https://youtube.com/watch?v=VIDEO_ID"

# Test with specific channel
python src/utils/video_tester.py --url "https://youtube.com/watch?v=VIDEO_ID" --channel wildnatureus2024

----------

# Use temporary directories for all output
python src/utils/video_tester.py --file video.mp4 --temp-dirs

# Keep files and use debug logging
python src/utils/video_tester.py --url "https://youtube.com/watch?v=VIDEO_ID" --no-cleanup --log-level DEBUG
'''