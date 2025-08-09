#!/usr/bin/env python3
import logging
import time
import random
from typing import Dict, Any
from googleapiclient.errors import HttpError
import config
from googleapiclient.http import MediaFileUpload
import argparse
import sys

def init_youtube_client():
    """Initialize YouTube upload client with error handling."""
    try:
        return config.get_upload_client()
    except Exception as e:
        logging.error("Failed to initialize YouTube client: %s", e)
        raise

def upload_youtube_short(client, video_path: str, metadata: Dict[str, Any], max_retries: int = 3):
    """
    Upload a video to YouTube as a Short with rate limiting and retry logic.
    """
    logging.info("Uploading YouTube Short: %s", metadata.get("title", "Unknown"))
    
    # Prepare upload metadata
    body = {
        'snippet': {
            'title': metadata.get('title', 'Untitled Video')[:100],  # Max 100 chars
            'description': metadata.get('description', ''),
            'tags': metadata.get('tags', [])[:500],  # YouTube allows up to 500 tags
            'categoryId': str(metadata.get('category_id', '15')),
            'defaultLanguage': 'en',
            'defaultAudioLanguage': 'en'
        },
        'status': {
            'privacyStatus': metadata.get('privacy_status', 'public'),
            'selfDeclaredMadeForKids': False
        }
    }
    
    # Add #Shorts to description if not present
    if '#Shorts' not in body['snippet']['description']:
        body['snippet']['description'] = f"{body['snippet']['description']}\n\n#Shorts"
    
    # Upload with retries and exponential backoff
    for attempt in range(max_retries):
        try:
            # Add jitter to avoid thundering herd
            if attempt > 0:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logging.info("Retrying upload in %.1f seconds (attempt %d/%d)", delay, attempt + 1, max_retries)
                time.sleep(delay)
            
            # Perform upload
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            request = client.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            response = request.execute()
            video_id = response['id']
            
            logging.info("✓ Successfully uploaded YouTube Short: https://youtube.com/watch?v=%s", video_id)
            return video_id
            
        except HttpError as e:
            error_code = e.resp.status
            error_content = e.content.decode('utf-8') if e.content else 'Unknown error'
            
            if error_code == 403:
                if 'quotaExceeded' in error_content:
                    logging.error("YouTube API quota exceeded. Stopping uploads.")
                    raise Exception("YouTube API quota exceeded")
                elif 'uploadLimitExceeded' in error_content:
                    logging.error("Daily upload limit exceeded. Will retry tomorrow.")
                    raise Exception("Daily upload limit exceeded")
            
            elif error_code == 400:
                logging.error("Bad request error: %s", error_content)
                # Don't retry on 400 errors - they're usually permanent
                raise
            
            elif error_code in [500, 502, 503, 504]:
                # Server errors - retry
                logging.warning("Server error %d on attempt %d: %s", error_code, attempt + 1, error_content)
                if attempt == max_retries - 1:
                    raise Exception(f"Upload failed after {max_retries} attempts: {error_content}")
                continue
            
            else:
                logging.error("Unexpected HTTP error %d: %s", error_code, error_content)
                raise
                
        except Exception as e:
            logging.error("Upload attempt %d failed: %s", attempt + 1, e)
            if attempt == max_retries - 1:
                raise Exception(f"Upload failed after {max_retries} attempts: {str(e)}")
    
    raise Exception("Upload failed - all retries exhausted")

def check_quota_usage(client):
    """Check current quota usage (if possible)."""
    try:
        # This is a lightweight request to check if API is working
        response = client.channels().list(part='id', mine=True).execute()
        return True
    except HttpError as e:
        if 'quotaExceeded' in str(e):
            return False
        raise

def upload_clip(youtube, filepath: str, metadata: dict, subtitle_path: str) -> str:
    """
    Uploads a single short to YouTube with captions.
    - youtube: client from init_youtube_client()
    - filepath: path to .mp4 file
    - metadata: {'title':..., 'description':..., 'tags':[...]}
    - subtitle_path: path to .srt file
    """
    body = {
        "snippet": {
            "title":       metadata["title"],
            "description": metadata["description"],
            "tags":        metadata.get("tags", []),
            "categoryId":  "15",  # Film & Animation (change as needed)
        },
        "status": {
            "privacyStatus":        "public",
            "selfDeclaredMadeForKids": False
        }
    }
    media = MediaFileUpload(filepath, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = request.execute()
    vid = response["id"]
    logging.info(f"Uploaded video {vid}")

    # Upload subtitles
    youtube.captions().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": vid,
                "language": "en",
                "name": "English subtitles",
                "isDraft": False
            }
        },
        media_body=MediaFileUpload(subtitle_path)
    ).execute()
    logging.info(f"Uploaded subtitles for {vid}")

    return vid

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Smoke-test YouTube uploader (init_youtube_client + upload_clip)"
    )
    parser.add_argument(
        "video_path",
        help="Path to a small test MP4 file to upload"
    )
    parser.add_argument(
        "subtitle_path",
        help="Path to a corresponding SRT subtitle file"
    )
    parser.add_argument(
        "--title",
        default="Test Upload",
        help="Video title for the test upload"
    )
    parser.add_argument(
        "--description",
        default="This is a smoke-test upload.",
        help="Video description"
    )
    parser.add_argument(
        "--tags",
        default="test,automation,youtube",
        help="Comma-separated list of tags"
    )
    args = parser.parse_args()

    # 1) Init client
    print("\n== Testing init_youtube_client ==")
    try:
        yt = init_youtube_client()
        print("✔ Got YouTube client:", yt)
    except Exception:
        logging.exception("init_youtube_client failed")
        sys.exit(1)

    # 2) Upload clip
    print("\n== Testing upload_clip ==")
    metadata = {
        "title": args.title,
        "description": args.description,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()]
    }
    try:
        vid_id = upload_clip(
            yt,
            args.video_path,
            metadata,
            args.subtitle_path
        )
        print(f"✔ upload_clip succeeded, video ID = {vid_id}")
    except Exception:
        logging.exception("upload_clip failed")
        sys.exit(1)

    print("\n== YouTube uploader smoke-test completed ==\n")
