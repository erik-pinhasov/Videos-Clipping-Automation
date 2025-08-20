#!/usr/bin/env python3
"""
WORKING YouTube automation - no BS, just results.
"""

from datetime import datetime
import sys
import signal
import time
from pathlib import Path
import openai
import os
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def signal_handler(sig, frame):
    print("\n🛑 Stopped")
    sys.exit(0)

def main():
    try:
        print("🚀 YouTube Shorts Automation - CONTINUOUS MODE")
        signal.signal(signal.SIGINT, signal_handler)
        
        # Import
        import config
        from src.core.logger import setup_logging, get_logger
        from src.services.content_manager import ContentManager
        from src.services.video_processor import VideoProcessor
        from src.services.uploader import VideoUploader
        from src.core.cleanup import ResourceCleaner
        
        # Setup
        setup_logging("INFO")
        logger = get_logger(__name__)
        cfg = config.Config()
        content_manager = ContentManager(cfg)
        video_processor = VideoProcessor(cfg)
        video_uploader = VideoUploader(cfg)
        cleaner = ResourceCleaner()
        
        # Load API key from .env
        load_dotenv()
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # CONTINUOUS LOOP - Process 1 video at a time
        processed_count = 0
        
        while True:
            logger.info(f"\n🔄 Starting processing cycle #{processed_count + 1}")
            logger.info("🔍 Finding next YouTube video...")
            
            # Get just 1 video (next in rotation)
            videos = content_manager.get_next_video()
            
            if not videos:
                logger.info("📭 No new videos available")
                logger.info("⏳ Waiting 30 minutes before checking again...")
                time.sleep(1800)  # 30 minutes
                continue
            
            video = videos[0]  # Just 1 video
            processed_count += 1
            
            logger.info(f"\n📹 Processing video #{processed_count}:")
            logger.info(f"   Title: {video['title']}")
            logger.info(f"   Channel: {video['channel']}")
            logger.info(f"   Duration: {video['duration_str']}")
            logger.info(f"   URL: {video['url']}")
            
            try:
                # Download video
                logger.info(f"   🔄 Downloading video...")
                video_path = video_processor.download_video(video['url'], cfg.DOWNLOAD_DIR)
                
                # Create clips
                logger.info(f"   ✂️ Creating clips...")
                clips = video_processor.create_clips(video_path, cfg.CLIPS_DIR)
                
                # Upload clips
                for clip in clips:
                    logger.info(f"   📤 Uploading clip to YouTube...")
                    video_uploader.upload_to_youtube(clip, video['title'], video['channel'])
                    
                    logger.info(f"   📤 Uploading clip to Rumble...")
                    video_uploader.upload_to_rumble(clip, video['title'], video['channel'])
                
                # Mark video as processed
                content_manager.mark_video_used(video['url'])
                logger.info(f"✅ Video #{processed_count} completed successfully!")
                
                # Clean up temporary files
                logger.info(f"🧹 Cleaning up temporary files...")
                cleaner.cleanup_video_files(video['id'])
                
                # Log OpenAI usage
                log_openai_usage()
                
                # Wait before processing the next video
                logger.info("⏳ Waiting 5 minutes before next video...")
                time.sleep(300)  # 5 minutes between videos
                
            except Exception as e:
                logger.error(f"❌ Failed to process video #{processed_count}: {e}")
                logger.info("⏳ Waiting 10 minutes before retry...")
                time.sleep(600)  # 10 minutes on error
                continue
        
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped after processing {processed_count} videos")
    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        import traceback
        traceback.print_exc()

def log_openai_usage():
    """Log OpenAI API usage to a file."""
    try:
        # Fetch usage details
        usage = openai.Usage.retrieve()
        total_tokens = usage.get("total_tokens", 0)
        total_cost = usage.get("total_cost", 0.0)
        
        # Log usage
        with open("openai_usage.log", "a") as log_file:
            log_file.write(f"{datetime.now()} - Total Tokens: {total_tokens}, Total Cost: ${total_cost:.2f}\n")
        
        print(f"🔍 OpenAI Usage: {total_tokens} tokens used, ${total_cost:.2f} spent.")
    except Exception as e:
        print(f"⚠️ Failed to fetch OpenAI usage: {e}")

if __name__ == "__main__":
    main()