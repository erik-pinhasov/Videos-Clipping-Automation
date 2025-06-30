import os
import logging
from yt_dlp import YoutubeDL

from config import DOWNLOAD_DIR

logger = logging.getLogger(__name__)

def get_youtube_metadata(url: str):
    """Returns (title, description, tags) for a YouTube URL."""
    opts = { "quiet": True, "skip_download": True }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info.get("title", ""), info.get("description", ""), info.get("tags", [])

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_videos(url: str) -> str:
    """
    Download the given YouTube video URL using yt-dlp.
    Returns the path to the downloaded video file.
    """
    video_id = url.split("v=")[-1]
    filepath = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    # if we've already downloaded it, just reuse it
    if os.path.exists(filepath):
        logging.info(f"Found existing file {filepath}, skipping download.")
        return filepath

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'outtmpl': filepath,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4'
    }
    logger.info("Starting download: %s", url)
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get('id')
        ext = info.get('ext', 'mp4')
        filename = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
    logger.info("Downloaded to %s", filename)
    return filename
