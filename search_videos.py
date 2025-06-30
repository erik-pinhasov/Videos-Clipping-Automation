# search_videos.py
import os
import json
import logging
from googleapiclient.discovery import build
import isodate

from config import YOUTUBE_API_KEY, CHANNELS, MAX_VIDEO_DURATION, USED_FILE

def _load_used_ids():
    if not os.path.exists(USED_FILE):
        return set()
    with open(USED_FILE, "r") as f:
        try:
            return set(json.load(f))
        except json.JSONDecodeError:
            return set()

def _save_used_ids(ids):
    with open(USED_FILE, "w") as f:
        json.dump(list(ids), f, indent=2)

def _get_channel_id(youtube, identifier):
    if identifier.startswith("UC"):
        return identifier
    resp = youtube.channels().list(
        part="id", forUsername=identifier, maxResults=1
    ).execute().get("items", [])
    if resp:
        return resp[0]["id"]
    resp = youtube.search().list(
        part="snippet", q=identifier, type="channel", maxResults=1
    ).execute().get("items", [])
    if resp:
        return resp[0]["snippet"]["channelId"]
    raise ValueError(f"Could not resolve channel: {identifier}")

def search_cc_videos(cfg):
    youtube = build("youtube", "v3", developerKey=cfg.YOUTUBE_API_KEY)
    used_ids = _load_used_ids()
    selected = []

    logging.info("Selecting one unused video per channel…")
    for ch in cfg.CHANNELS:
        ch_id = _get_channel_id(youtube, ch)
        logging.info(f" → Channel {ch} (ID={ch_id})")

        # grab top 5 by views
        items = youtube.search().list(
            part="id,snippet",
            channelId=ch_id,
            type="video",
            order="viewCount",
            maxResults=5
        ).execute().get("items", [])

        for it in items:
            vid = it["id"]["videoId"]
            if vid in used_ids:
                continue
            # check duration
            info = youtube.videos().list(
                part="contentDetails,snippet", id=vid
            ).execute().get("items", [])
            if not info:
                continue
            dur = isodate.parse_duration(
                info[0]["contentDetails"]["duration"]
            ).total_seconds()
            if dur > cfg.MAX_VIDEO_DURATION:
                logging.info(f"    skipping {vid}: {dur/60:.1f} min")
                continue

            # select it
            title = info[0]["snippet"]["title"]
            selected.append({
                "id": vid,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "duration": int(dur),
            })
            used_ids.add(vid)
            logging.info(f"    picked {vid} ({dur/60:.1f} min): {title}")
            break

    if not selected:
        logging.warning("No new videos found — clearing used list and retrying first channel.")
        used_ids.clear()
        _save_used_ids(used_ids)
        # now just grab the top video from CHANNELS[0]
        first = cfg.CHANNELS[0]
        ch_id = _get_channel_id(youtube, first)
        top = youtube.search().list(
            part="id,snippet", channelId=ch_id, type="video",
            order="viewCount", maxResults=1
        ).execute().get("items", [])
        if top:
            vid = top[0]["id"]["videoId"]
            info = youtube.videos().list(
                part="contentDetails,snippet", id=vid
            ).execute().get("items", [])[0]
            dur = isodate.parse_duration(
                info["contentDetails"]["duration"]
            ).total_seconds()
            selected.append({
                "id": vid,
                "title": info["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={vid}",
                "duration": int(dur),
            })
            used_ids.add(vid)
            logging.info(f"    fallback pick {vid} ({dur/60:.1f} min)")

    return selected

def mark_video_used(video_id):
    """
    After fully processing a video (download, Rumble, Shorts),
    call this to record it so we never pick it again.
    """
    ids = _load_used_ids()
    ids.add(video_id)
    _save_used_ids(ids)