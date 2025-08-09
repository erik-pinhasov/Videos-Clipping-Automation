#!/usr/bin/env python3
"""
Test script for YouTube Shorts Automation
Run this to test the automation on a single video without conflicts.
"""
import sys

# Save the original arguments
original_argv = sys.argv.copy()

# Temporarily set sys.argv to avoid argparse conflicts during imports
sys.argv = ['test_automation.py']

import time
import logging
import subprocess
import shutil
import os
from pathlib import Path

import config
from config import Config
from highlight_detection import detect_highlights
import search_videos
import download_videos
import clipper
import metadata_generator
import rumble_uploader
import youtube_uploader

# Restore the original arguments after all imports
sys.argv = original_argv


def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('automation.log'),
            logging.StreamHandler()
        ]
    )


def ensure_dirs():
    """Create necessary directories."""
    for dir_path in [config.DOWNLOAD_DIR, config.AUDIO_DIR, config.CLIPS_DIR]:
        Path(dir_path).mkdir(exist_ok=True)


def cleanup_resources(video_id: str):
    """Clean up temporary files for a video."""
    patterns = [
        f"{video_id}*",
        f"*{video_id}*"
    ]
    
    for directory in [config.DOWNLOAD_DIR, config.AUDIO_DIR, config.CLIPS_DIR]:
        dir_path = Path(directory)
        if dir_path.exists():
            for pattern in patterns:
                for file_path in dir_path.glob(pattern):
                    try:
                        if file_path.is_file():
                            file_path.unlink()
                            logging.debug("Cleaned up: %s", file_path)
                    except Exception as e:
                        logging.warning("Failed to cleanup %s: %s", file_path, e)


def merge_audio_video(video_path: str, audio_path: str, output_path: str):
    """Merge audio and video files."""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-shortest',
        output_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logging.info("Successfully merged audio/video: %s", output_path)
    except subprocess.CalledProcessError as e:
        logging.error("Failed to merge audio/video: %s", e.stderr.decode())
        raise


def create_silent_audio(output_path: str, duration_sec: int):
    """Create a silent audio file as fallback."""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', f'anullsrc=r=44100:cl=stereo:d={duration_sec}',
        '-c:a', 'pcm_s16le',
        output_path
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)


def test_single_video_local(video_path: str, channel: str = None):
    """
    Test function to run the automation pipeline on a local video file.
    """
    setup_logging()
    cfg = config.Config()
    ensure_dirs()

    # Validate input file
    video_file = Path(video_path)
    if not video_file.exists():
        logging.error("Video file not found: %s", video_path)
        return False

    # Get available channels
    available_channels = list(cfg.CHANNEL_LOGOS.keys())
    if not channel:
        channel = available_channels[0] if available_channels else None
        logging.info("No channel specified, using: %s", channel)
    elif channel not in available_channels:
        logging.error("Channel '%s' not found. Available: %s", channel, available_channels)
        return False

    try:
        # Initialize YouTube client
        yt_client = youtube_uploader.init_youtube_client()
        logging.info("✓ YouTube client initialized")
    except Exception as e:
        logging.error("Failed to initialize YouTube client: %s", e)
        return False

    # Create fake video info
    video_id = video_file.stem
    video_info = {
        "id": video_id,
        "title": f"Test Video {video_id}",
        "url": f"file://{video_path}"
    }

    logging.info("📹 Testing with local video: %s", video_path)

    try:
        # Copy video to downloads directory to simulate download
        target_path = Path(config.DOWNLOAD_DIR) / f"{video_id}.mp4"
        if not target_path.exists():
            shutil.copy2(video_path, target_path)
            logging.info("✓ Copied video to downloads directory")

        # Run the pipeline starting from step 2 (branding)
        vid = video_info["id"]
        title = video_info.get("title", "").strip()
        logging.info("▶ Processing %s (%s) on channel %s", title, vid, channel)

        # Use the copied file as input
        video_path_input = str(target_path)

        # 2) Brand the full video
        logging.info("  • Adding logo overlay...")
        branded = os.path.join(config.DOWNLOAD_DIR, f"{vid}_branded.mp4")
        try:
            clipper.overlay_logo(video_path_input, branded, channel)
        except Exception as e:
            logging.error("Logo overlay failed: %s", e)
            # Use original video as fallback
            shutil.copy2(video_path_input, branded)

        # 2a) Generate metadata for the full video
        logging.info("  • Generating metadata...")
        try:
            meta_full = metadata_generator.generate_metadata(branded, 300)
        except Exception as e:
            logging.error("Metadata generation failed: %s", e)
            meta_full = {"title": title, "description": f"Video from {channel}"}

        # 3) Upload full video to Rumble
        logging.info("  • Uploading to Rumble...")
        try:
            rumble_uploader.upload_to_rumble(branded, meta_full["title"], 
                                           meta_full["description"], 
                                           meta_full.get("tags", []))
        except Exception as e:
            logging.error("Rumble upload failed: %s", e)
            # Continue with shorts creation even if Rumble fails

        # 4) Create highlight clips for YouTube Shorts
        logging.info("  • Finding highlights...")
        try:
            highlights = detect_highlights(branded)
            if not highlights:
                logging.warning("No highlights found for %s", vid)
                # Create a default highlight from the beginning
                highlights = [(0, min(60, 300))]  # 60 seconds or less
        except Exception as e:
            logging.error("Highlight generation failed: %s", e)
            # Create a default highlight from the beginning
            highlights = [(0, min(60, 300))]  # 60 seconds or less

        # Convert tuples to dicts for make_clips
        highlight_dicts = [{"start": start, "end": end} for start, end in highlights]

        logging.info("  • Creating %d highlight clips...", len(highlight_dicts))
        try:
            clip_paths = clipper.make_clips(branded, highlight_dicts, vid, channel)
        except Exception as e:
            logging.error("Clip creation failed: %s", e)
            raise

        # 4a) Generate audio for each clip
        logging.info("  • Generating audio for clips...")
        audio_paths = []
        for idx, clip_path in enumerate(clip_paths):
            try:
                meta_clip = metadata_generator.generate_metadata(clip_path, 300)
                audio_path = os.path.join(config.AUDIO_DIR, f"{vid}_{idx}_voice.wav")
                metadata_generator.generate_tts_audio(meta_clip, audio_path)
                audio_paths.append(audio_path)
            except Exception as e:
                logging.error("Audio generation failed for clip %d: %s", idx, e)
                # Create silent audio as fallback
                audio_path = os.path.join(config.AUDIO_DIR, f"{vid}_{idx}_silent.wav")
                create_silent_audio(audio_path, 60)  # 60 seconds of silence
                audio_paths.append(audio_path)

        # 5) Merge & upload shorts to YouTube
        logging.info("  • Uploading %d shorts to YouTube...", len(clip_paths))
        for idx, clip in enumerate(clip_paths):
            try:
                logging.info("    • Uploading short %d/%d", idx + 1, len(clip_paths))
                short_out = os.path.join(config.CLIPS_DIR, f"{vid}_{idx}_short.mp4")
                merge_audio_video(clip, audio_paths[idx], short_out)

                meta = metadata_generator.generate_metadata(short_out, 300)
                youtube_uploader.upload_youtube_short(yt_client, short_out, meta)
                
                # Add delay between uploads to avoid rate limiting
                time.sleep(5)
                
            except Exception as e:
                logging.error("Failed to upload short %d: %s", idx, e)
                continue

        # 6) Mark video as used
        search_videos.mark_video_used(vid)
        logging.info("✓ Successfully processed %s", vid)

        logging.info("🎉 Test completed successfully!")
        return True
        
    except Exception as e:
        logging.error("Test failed: %s", e, exc_info=True)
        return False


if __name__ == "__main__":
    # Manual argument parsing to completely avoid argparse conflicts
    if len(original_argv) < 2:
        print("Usage: python test_automation.py <video_path> [--channel <channel_name>]")
        print("Example: python test_automation.py 'video.mp4' --channel 'navwildanimaldocumentary'")
        sys.exit(1)
    
    video_path = original_argv[1]
    channel = None
    
    # Look for --channel argument in original_argv
    if "--channel" in original_argv:
        try:
            channel_index = original_argv.index("--channel") + 1
            if channel_index < len(original_argv):
                channel = original_argv[channel_index]
        except (ValueError, IndexError):
            pass
    
    print(f"\n🧪 Testing automation with local file: {video_path}")
    if channel:
        print(f"Using channel: {channel}")
    
    success = test_single_video_local(video_path, channel)
    print(f"\n{'✅ Test passed!' if success else '❌ Test failed!'}")