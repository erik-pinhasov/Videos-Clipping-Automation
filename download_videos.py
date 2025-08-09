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

if __name__ == "__main__":
    import logging
    import sys

    logging.basicConfig(level=logging.INFO)
    TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # short, fast test video

    print("\n== Testing metadata extraction ==")
    try:
        title, description, tags = get_youtube_metadata(TEST_URL)
        print(f"Title      : {title}")
        print(f"Description: {description[:100]}{'...' if len(description)>100 else ''}")
        print(f"Tags       : {tags}\n")
    except Exception as e:
        logging.exception("Metadata extraction failed")

    print("== Testing video download ==")
    try:
        path = download_videos(TEST_URL)
        print(f"Downloaded file path: {path}\n")
    except Exception as e:
        logging.exception("Download failed")

    print("== All tests completed ==\n")
