import os
import logging
from config import get_upload_client
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# Default privacy status for uploaded Shorts
PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY", "public")


def upload_video(clip_path: str, metadata: dict) -> dict:
    """
    Upload a video clip to YouTube Shorts with given metadata.

    Args:
        clip_path: Path to the video clip file.
        metadata: Dict with keys 'title', 'description', 'hashtags'.

    Returns:
        API response dict including uploaded video ID and URL.
    """
    logger.info("Initializing YouTube upload client")
    youtube = get_upload_client()

    title = metadata.get("title", "")
    description = metadata.get("description", "")
    hashtags = metadata.get("hashtags", [])
    tags = [tag for tag in hashtags if tag.startswith("#")]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22"  # People & Blogs category (change if needed)
        },
        "status": {
            "privacyStatus": PRIVACY_STATUS
        }
    }

    logger.info("Uploading clip '%s' with title '%s'", clip_path, title)
    media = MediaFileUpload(clip_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    try:
        response = request.execute()
        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        logger.info("Upload successful: %s", video_url)
        return {"id": video_id, "url": video_url}
    except Exception as e:
        logger.error("Failed to upload %s: %s", clip_path, e)
        raise
