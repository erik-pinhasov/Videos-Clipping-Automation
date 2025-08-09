# search_videos.py
import os
import json
import logging
import isodate
from pathlib import Path

import config

def mark_video_used(video_id: str) -> None:
    """Add video_id to our used_videos.json file so we skip it next time."""
    used_file = Path(config.USED_FILE)
    if used_file.exists():
        with open(used_file, 'r') as f:
            used_data = json.load(f)
    else:
        used_data = {"used_video_ids": []}
    
    if video_id not in used_data["used_video_ids"]:
        used_data["used_video_ids"].append(video_id)
    
    with open(used_file, 'w') as f:
        json.dump(used_data, f, indent=2)

def search_cc_videos(cfg: config.Config):
    """
    Search for Creative Commons videos from configured channels.
    Returns a list of {id, title, url} dicts.
    """
    client = cfg.get_search_client()
    used_file = Path(cfg.USED_FILE)
    
    if used_file.exists():
        with open(used_file, 'r') as f:
            used_data = json.load(f)
        used_ids = set(used_data.get("used_video_ids", []))
    else:
        used_ids = set()

    results = []
    
    for channel_name in cfg.CHANNEL_LOGOS:
        logging.info("Searching channel: %s", channel_name)
        
        try:
            # Search for videos from this channel
            search_response = client.search().list(
                q=f"site:youtube.com/c/{channel_name} OR site:youtube.com/@{channel_name}",
                part="id,snippet",
                maxResults=10,
                type="video",
                videoLicense="creativeCommon",  # Only CC videos
                order="date"
            ).execute()

            for item in search_response.get("items", []):
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                
                if video_id in used_ids:
                    logging.info("  ⏭ Skipping used video: %s", title)
                    continue
                
                # Get video details to check duration
                video_response = client.videos().list(
                    part="contentDetails",
                    id=video_id
                ).execute()
                
                if video_response["items"]:
                    duration_str = video_response["items"][0]["contentDetails"]["duration"]
                    duration_sec = isodate.parse_duration(duration_str).total_seconds()
                    
                    if duration_sec <= cfg.MAX_VIDEO_DURATION:
                        results.append({
                            "id": video_id,
                            "title": title,
                            "url": f"https://www.youtube.com/watch?v={video_id}"
                        })
                        logging.info("  ✓ Found video: %s (%.1fs)", title, duration_sec)
                    else:
                        logging.info("  ⏭ Skipping long video: %s (%.1fs)", title, duration_sec)
        
        except Exception as e:
            logging.error("Error searching channel %s: %s", channel_name, e)
    
    return results
