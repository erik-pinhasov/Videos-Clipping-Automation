from datetime import datetime
import sys
import signal
import time
from pathlib import Path
import openai
import os
from dotenv import load_dotenv
import config
from src.core.logger import setup_logging, get_logger
from src.services.content_manager import ContentManager
from src.services.metadata_service import MetadataService
from src.services.video_processor import VideoProcessor
from src.services.uploader import VideoUploader
from src.core.cleanup import ResourceCleaner

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def signal_handler(sig, frame):
    print("\n🛑 Stopped")
    sys.exit(0)

def main():
    try:
        print("🚀 YouTube Shorts Automation - CONTINUOUS MODE")
        signal.signal(signal.SIGINT, signal_handler)

        # Setup
        setup_logging("INFO")
        logger = get_logger(__name__)
        cfg = config.Config()
        video_processor = VideoProcessor(cfg)
        video_uploader = VideoUploader(cfg)
        video_uploader.initialize()
        metadata_service = MetadataService(cfg)

        # CONTINUOUS LOOP - Process 1 video at a time
        processed_count = 0

        while True:
            logger.info(f"\n🔄 Starting processing cycle #{processed_count + 1}")
            logger.info("🔍 Finding next YouTube video...")

            # Get next video
            videos = video_processor.content_manager.get_new_videos()
            if not videos:
                logger.info("📭 No new videos available")
                logger.info("⏳ Waiting 30 minutes before checking again...")
                time.sleep(1800)  # 30 minutes
                continue

            video = videos[0]  # Process one video at a time
            processed_count += 1

            try:
                logger.info(f"\n📹 Processing video from channel: {video['channel']}")
                logger.info(f"   Title: {video['title']}")
                logger.info(f"   Duration: {video['duration_str']}")
                logger.info(f"   URL: {video['url']}")

                # Step 1: Download video
                while True:
                    try:
                        logger.info(f"   🔄 Downloading video...")
                        video_path = video_processor.download_video(video['url'])
                        break
                    except Exception as e:
                        logger.error(f"❌ Failed to download video: {e}")
                        wait_for_manual_fix()

                # Step 2: Add logo overlay
                while True:
                    try:
                        logger.info(f"   🖼️ Adding logo overlay...")
                        branded_video_path = video_processor.add_logo(video_path, cfg.CLIPS_DIR, video['channel'])
                        break
                    except Exception as e:
                        logger.error(f"❌ Failed to add logo: {e}")
                        wait_for_manual_fix()

                # Step 3: Generate metadata
                while True:
                    try:
                        logger.info(f"   🧠 Generating metadata...")
                        metadata = metadata_service.generate(video_path, video['channel'], video['title'])
                        logger.info(f"   ✅ Metadata generated: {metadata}")
                        break
                    except Exception as e:
                        logger.error(f"❌ Failed to generate metadata: {e}")
                        wait_for_manual_fix()


                # Step 4: Upload full video to Rumble
                try:
                    logger.info(f"   📤 Uploading full video to Rumble...")
                    video_uploader.upload_to_rumble(
                        branded_video_path,
                        metadata['title'],
                        metadata['description'],
                        metadata['tags']
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to upload to Rumble: {e}")
                    wait_for_manual_fix()
                    # Continue to clip creation even if Rumble upload fails

                # Step 5: Create clips from the branded video
                while True:
                    try:
                        logger.info(f"   ✂️ Creating clips...")
                        clips = video_processor.create_clips(branded_video_path, cfg.CLIPS_DIR, video['id'], video['channel'])
                        break
                    except Exception as e:
                        logger.error(f"❌ Failed to create clips: {e}")
                        wait_for_manual_fix()

                # Step 6: Upload clips to YouTube Shorts
                uploaded_count = 0
                for clip in clips:
                    while True:
                        try:
                            logger.info(f"   📤 Uploading clip to YouTube Shorts...")
                            ok = video_uploader.upload_to_youtube(clip, metadata)
                            if ok:
                                uploaded_count += 1
                            break
                        except Exception as e:
                            logger.error(f"❌ Failed to upload clip to YouTube Shorts: {e}")
                            wait_for_manual_fix()

                # Step 7: Mark original video used only if Rumble succeeded (best-effort) and all shorts uploaded
                try:
                    if uploaded_count == len(clips):
                        video_processor.content_manager.mark_video_used(video['url'])
                    else:
                        logger.warning(f"Only {uploaded_count}/{len(clips)} clips uploaded. Not marking source as used.")
                except Exception as e:
                    logger.debug(f"Could not mark used_videos: {e}")

                # Step 8: Optional cleanup: delete branded/full files if configured
                try:
                    if getattr(cfg, 'CLEANUP_DELETE_BRANDED', True):
                        p = Path(branded_video_path)
                        if p.exists():
                            p.unlink()
                            logger.info(f"🧹 Deleted branded file: {p.name}")
                    if getattr(cfg, 'CLEANUP_DELETE_ORIGINAL_DOWNLOAD', True):
                        p = Path(video_path)
                        if p.exists():
                            p.unlink()
                            logger.info(f"🧹 Deleted original download: {p.name}")
                except Exception as e:
                    logger.debug(f"Cleanup failed: {e}")

                logger.info(f"✅ Video processed successfully!")

            except Exception as e:
                logger.error(f"❌ Failed to process video: {e}")
                wait_for_manual_fix()

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

def wait_for_manual_fix():
    """Wait for manual intervention before retrying."""
    input("⚠️ Error occurred. Fix the issue and press Enter to retry...")

if __name__ == "__main__":
    main()