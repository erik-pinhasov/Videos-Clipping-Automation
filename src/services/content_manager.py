import json
import yt_dlp
import config
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.core.logger import get_logger


class ContentManager:
    """Manages content discovery and tracking from YouTube channels."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Track processed videos
        self.used_videos_file = "used_videos.json"
        
        # Configured YouTube channels
        self.channel_urls = self.config.YOUTUBE_CHANNELS
    
    def get_new_videos(self) -> List[Dict[str, Any]]:
        """Get new unprocessed videos from configured YouTube channels."""
        self.logger.info("🔍 Discovering videos from YouTube channels...")
        
        used_videos = self._load_used_videos()
        all_videos = []
        
        for channel_name, channel_url in self.channel_urls.items():
            self.logger.info(f"  📺 Checking {channel_name}...")
            
            try:
                videos = self._get_real_videos(channel_url, channel_name, used_videos)
                if videos:
                    # Take only the FIRST (newest) video from this channel
                    all_videos.append(videos[0])
                    self.logger.info(f"    ✅ Selected 1 video: {videos[0]['title'][:50]}...")
                else:
                    self.logger.info(f"    ❌ No videos found")
                
            except Exception as e:
                self.logger.error(f"    ❌ Failed {channel_name}: {e}")
                continue
        # Sort by upload date (newest first); coerce None to '' to avoid TypeError
        all_videos.sort(key=lambda x: (x.get('upload_date') or ''), reverse=True)
        
        self.logger.info(f"🎯 Total videos selected: {len(all_videos)} (1 per channel)")
        return all_videos  # Return 1 video per channel (max 4 total)
    
    def _get_real_videos(self, channel_url: str, channel_name: str, used_videos: set) -> List[Dict[str, Any]]:
        """Extract video information from YouTube channel using yt-dlp."""
        
        # First pass: use extract_flat to list recent entries quickly and avoid format probing errors
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,   # Only lightweight metadata in channel listing
            'playlistend': 20,      # Check last 20
            'ignoreerrors': True,
        }
        
        videos = []
        cutoff_date = datetime.now() - timedelta(days=self.config.MAX_VIDEO_AGE_DAYS)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                self.logger.info(f"    🔄 Extracting info from {channel_name}...")
                self.logger.info(f"    🌐 URL: {channel_url}")
                
                # Extract playlist
                playlist_info = ydl.extract_info(channel_url, download=False)
                
                self.logger.info(f"    📊 Raw playlist info keys: {list(playlist_info.keys()) if playlist_info else 'None'}")
                
                if not playlist_info or 'entries' not in playlist_info:
                    self.logger.warning(f"    ⚠️ No entries found for {channel_name}")
                    self.logger.warning(f"    📋 Playlist info: {playlist_info}")
                    return []
                
                total_entries = len(playlist_info['entries'])
                self.logger.info(f"    📺 Found {total_entries} total entries")
                
                processed = 0
                for entry in playlist_info['entries']:
                    processed += 1
                    self.logger.info(f"    🔍 Processing entry {processed}/{total_entries}")
                    
                    if not entry or len(videos) >= 1:  # Max 1 per channel
                        self.logger.info(f"    ⏹️ Stopping at entry {processed} (found {len(videos)} videos)")
                        break
                    
                    try:
                        # Get basic video details from flat entry
                        video_id = entry.get('id')
                        title = entry.get('title', 'Untitled')
                        upload_date = entry.get('upload_date') or entry.get('release_date')
                        duration = entry.get('duration') or 0
                        view_count = entry.get('view_count') or 0
                        
                        self.logger.info(f"      📹 Video: {title[:50]}...")
                        self.logger.info(f"          ID: {video_id}")
                        # Ensure proper integer formatting for minutes:seconds
                        _dur_i = int(duration) if duration is not None else 0
                        self.logger.info(f"          Duration: {_dur_i}s ({_dur_i//60}:{_dur_i%60:02d})")
                        self.logger.info(f"          Upload: {upload_date}")
                        self.logger.info(f"          Views: {view_count:,}")
                        
                        if not video_id or not title:
                            self.logger.info(f"      ❌ SKIP: Missing ID or title")
                            continue
                        
                        # Check duration - USE CONFIG VALUES!
                        if not (self.config.MIN_VIDEO_DURATION <= duration <= self.config.MAX_VIDEO_DURATION):
                            self.logger.info(f"      ❌ SKIP: Duration {duration}s not in range {self.config.MIN_VIDEO_DURATION}-{self.config.MAX_VIDEO_DURATION}s")
                            continue
                        
                        # Check upload date
                        if upload_date:
                            try:
                                upload_dt = datetime.strptime(upload_date, '%Y%m%d')
                                if upload_dt < cutoff_date:
                                    self.logger.info(f"      ❌ SKIP: Too old ({upload_dt.date()})")
                                    continue
                            except Exception as date_error:
                                self.logger.info(f"      ⚠️ Date parse error: {date_error}")
                        
                        # Check if already used
                        video_url = f'https://www.youtube.com/watch?v={video_id}'
                        if video_url in used_videos:
                            self.logger.info(f"      ❌ SKIP: Already used")
                            continue
                        
                        # Filter unwanted content
                        title_lower = title.lower()
                        skip_terms = ['live', 'stream', '#shorts', 'compilation']
                        found_skip_term = None
                        for term in skip_terms:
                            if term in title_lower:
                                found_skip_term = term
                                break
                        
                        if found_skip_term:
                            self.logger.info(f"      ❌ SKIP: Contains '{found_skip_term}'")
                            continue
                        
                        # Second pass: fetch full metadata for the chosen video (no download)
                        try:
                            video_url_full = video_url
                            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl2:
                                full = ydl2.extract_info(video_url_full, download=False)
                                duration = full.get('duration', duration)
                                upload_date = full.get('upload_date', upload_date)
                                view_count = full.get('view_count', view_count)
                                title = full.get('title', title)
                        except Exception as fetch_err:
                            self.logger.debug(f"      ⚠️ Could not fetch full metadata: {fetch_err}")

                        # This is a good video!
                        video_info = {
                            'id': video_id,
                            'title': title,
                            'url': video_url,
                            'channel': channel_name,
                            'duration': duration,
                            'upload_date': upload_date,
                            'view_count': view_count,
                            'duration_str': f"{int(duration)//60}:{int(duration)%60:02d}"
                        }
                        
                        videos.append(video_info)
                        self.logger.info(f"      ✅ ACCEPTED: Added to list ({len(videos)}/5)")
                        
                    except Exception as e:
                        self.logger.info(f"      ❌ Entry error: {e}")
                        continue
                
                self.logger.info(f"    📊 Final result: {len(videos)} videos from {processed} entries")
            
            except Exception as e:
                self.logger.error(f"    ❌ yt-dlp failed for {channel_name}: {e}")
                import traceback
                self.logger.error(f"    📋 Full error: {traceback.format_exc()}")
                return []
        
        return videos
    
    def mark_video_used(self, video_url: str) -> None:
        """Mark video as processed."""
        try:
            used_videos = self._load_used_videos()
            used_videos.add(video_url)
            
            # Save to file
            with open(self.used_videos_file, 'w') as f:
                json.dump({
                    'used_videos': list(used_videos),
                    'last_updated': datetime.now().isoformat(),
                    'total_processed': len(used_videos)  # Changed from 'total_count'
                }, f, indent=2)
            
            self.logger.debug(f"✅ Marked as used: {video_url}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to mark video as used: {e}")
    
    def _load_used_videos(self) -> set:
        """Load used videos."""
        try:
            if Path(self.used_videos_file).exists():
                with open(self.used_videos_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('used_videos', []))
            return set()
        except:
            return set()