#!/usr/bin/env python3
import os
import logging

from config import Config
from search_videos import search_cc_videos, mark_video_used
from download_videos import download_videos
from clipper import clip_video, remove_logos
from rumble_uploader import upload_to_rumble
from subtitle_generator import transcribe_audio
from highlight_detection import select_highlight_clips
from metadata_generator import generate_metadata
from uploader import upload_video

def main():
    cfg = Config()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting full-pipeline (YouTube Shorts + Rumble)")

    # 1) Pick one unused video per channel
    videos = search_cc_videos(cfg)
    logger.info("Selected %d videos", len(videos))

    for vid in videos:
        vid_id = vid["id"]
        try:
            # → Download (or reuse)
            logger.info("Downloading full video: %s", vid_id)
            full_path = download_videos(vid["url"])

            # → Remove logos
            cleaned = os.path.splitext(full_path)[0] + "_cleaned.mp4"
            logger.info("Removing logos → %s", cleaned)
            cleaned_path = remove_logos(full_path, cleaned, True)

            # → Upload full video to Rumble
            logger.info("Uploading full to Rumble: %s", vid_id)
            upload_to_rumble(
                video_path=cleaned_path,
                title=vid["title"],
                description=f"Auto-uploaded from channel, ID {vid_id}",
                tags=["nature", "wildlife"]
            )
            logger.info("Full video uploaded to Rumble: %s", vid_id)

            # → Shorts pipeline
            logger.info("Transcribing audio…")
            transcript = transcribe_audio(cleaned_path)

            logger.info("Selecting highlight clips…")
            highlights = select_highlight_clips(transcript)
            logger.info("%d highlights chosen", len(highlights))

            logger.info("Creating clips…")
            clips = clip_video(cleaned_path, highlights, vid_id)

            logger.info("Generating metadata…")
            metas = [generate_metadata(c) for c in clips]

            for clip_path, meta in zip(clips, metas):
                logger.info("Uploading clip to YouTube: %s", clip_path)
                upload_video(clip_path, meta)
                logger.info("Uploaded clip: %s", clip_path)

        except Exception as e:
            logger.error("Error processing %s: %s", vid_id, e, exc_info=True)
            # skip marking so it can retry later
            continue

        # Mark it only after everything succeeded
        mark_video_used(vid_id)
        logger.info("Marked video as used: %s", vid_id)

    logger.info("Automation pipeline completed")

if __name__ == "__main__":
    main()
