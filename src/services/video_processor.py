import time
import signal
import os
import subprocess
import yt_dlp
import config
from pathlib import Path
from typing import List, Dict, Any
from src.core.logger import get_logger
from src.core.exceptions import VideoProcessingError, DownloadError
from src.services.content_manager import ContentManager
from src.services.clip_creator import ClipCreator
from src.services.branding import VideoBranding
from src.services.highlight_detector import HighlightDetector


class VideoProcessor:
    """Simple video processor with graceful shutdown."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        self.should_stop = False
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialize content manager
        self.content_manager = ContentManager(cfg)
    
    def _signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        self.logger.info("🛑 Graceful shutdown requested...")
        self.should_stop = True

    def _process_video(self, video: Dict[str, Any]) -> bool:
        """Process single video (simplified for now)."""
        try:
            # For now, just log the video info
            self.logger.info(f"  Title: {video['title']}")
            self.logger.info(f"  Channel: {video['channel']}")
            self.logger.info(f"  Duration: {video.get('duration', 'Unknown')} seconds")
            
            # Simulate processing time
            time.sleep(3)
            
            # Check for stop during processing
            if self.should_stop:
                return False
            
            # Mark as used (only on success)
            self.content_manager.mark_video_used(video['url'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Video processing failed: {e}")
            return False
    
    def download_video(self, url: str) -> str:
        """Download the given YouTube video URL using yt-dlp."""
        try:
            self.logger.info(f"🔄 Downloading video: {url}")
            # First, probe info without downloading to determine expected filename
            # Use default client and avoid cookies to prevent mobile-client cookie conflict
            expected_path = None
            probe_attempts = [
                {
                    'format': 'best',
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': True,
                },
                {
                    'format': 'best',
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': True,
                    'cookiefile': 'cookies.txt',
                }
            ]
            for pidx, popts in enumerate(probe_attempts, start=1):
                try:
                    with yt_dlp.YoutubeDL(popts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        expected_path = Path(ydl.prepare_filename(info))
                        break
                except Exception as e:
                    self.logger.debug(f"   Probe attempt {pidx} failed: {e}")
                    continue
            if expected_path is None:
                # Fallback: guess a filename in downloads
                expected_path = Path(self.config.DOWNLOAD_DIR) / f"{int(time.time())}.mp4"

            # Check if file already exists from previous run
            if expected_path.exists():
                self.logger.info(f"📦 Found existing download, reusing: {expected_path.name}")
                return str(expected_path)

            # Helper: build a high-quality format selector up to configured height
            def build_format_selector(max_h: int, prefer_av1: bool) -> str:
                # Order codecs: AV1 > VP9 > H.264 if preferred; otherwise VP9 > H.264
                vcodec_pref = (
                    'av01|av1|vp9|vp09|h264|avc1' if prefer_av1 else 'vp9|vp09|h264|avc1'
                )
                # Best separate video up to height, with codec preference, then bestaudio (m4a if possible)
                dash = f"bestvideo[height<={max_h}][vcodec~='^({vcodec_pref})'][protocol!=http_dash_segments]+bestaudio/best[height<={max_h}]"
                # Progressive MP4 fallback (often 720p or 360p)
                prog = "best[ext=mp4]/best"
                return f"{dash}/{prog}"

            fmt_selector = build_format_selector(self.config.DOWNLOAD_MAX_HEIGHT, self.config.DOWNLOAD_PREFER_AV1)

            # Not found, perform actual download with quality-first clients
            strategies = [
                # Try default web client first for max quality DASH
                {
                    'format': fmt_selector,
                    'merge_output_format': self.config.DOWNLOAD_MERGE_FORMAT,
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': False,
                    'retries': 5,
                    'fragment_retries': 5,
                },
                # TV client (often bypasses SABR)
                {
                    'format': fmt_selector,
                    'merge_output_format': self.config.DOWNLOAD_MERGE_FORMAT,
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': False,
                    'retries': 5,
                    'fragment_retries': 5,
                    'extractor_args': {'youtube': {'player_client': ['tv']}},
                },
                # iOS client
                {
                    'format': fmt_selector,
                    'merge_output_format': self.config.DOWNLOAD_MERGE_FORMAT,
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': False,
                    'retries': 5,
                    'fragment_retries': 5,
                    'extractor_args': {'youtube': {'player_client': ['ios']}},
                },
                # Android client (may warn about PO token)
                {
                    'format': fmt_selector,
                    'merge_output_format': self.config.DOWNLOAD_MERGE_FORMAT,
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': False,
                    'retries': 5,
                    'fragment_retries': 5,
                    'extractor_args': {'youtube': {'player_client': ['android']}},
                },
                # Last resort: default client with cookies, any best
                {
                    'format': 'best',
                    'merge_output_format': self.config.DOWNLOAD_MERGE_FORMAT,
                    'outtmpl': f"{self.config.DOWNLOAD_DIR}/%(title)s.%(ext)s",
                    'quiet': False,
                    'cookiefile': 'cookies.txt',
                    'retries': 5,
                    'fragment_retries': 5
                }
            ]

            last_err = None
            for idx, opts in enumerate(strategies, start=1):
                try:
                    client = opts.get('extractor_args', {}).get('youtube', {}).get('player_client', 'default')
                    self.logger.info(f"   ▶ Attempt {idx}/{len(strategies)} with client={client}, format={opts.get('format')}")
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        # After merge, yt-dlp may change extension to mkv/mp4; prefer requested merge format
                        final_path = Path(ydl.prepare_filename(info))
                        # If a merged file exists with different ext, pick it
                        merged_ext = self.config.DOWNLOAD_MERGE_FORMAT
                        candidate = final_path.with_suffix(f'.{merged_ext}')
                        if candidate.exists():
                            final_path = candidate
                        # Log resolution/codec for visibility
                        v = (info.get('requested_formats') or [info])[-1]
                        height = v.get('height') or info.get('height')
                        vcodec = v.get('vcodec') or info.get('vcodec')
                        acodec = v.get('acodec') or info.get('acodec')
                        self.logger.info(f"✅ Downloaded: {info.get('title')} | {height}p, vcodec={vcodec}, acodec={acodec}, file={final_path.name}")
                        return str(final_path)
                except Exception as e:
                    last_err = e
                    self.logger.warning(f"   ⚠️ Download attempt {idx} failed: {e}")
                    continue

            # All strategies failed
            raise DownloadError(f"Failed to download video after retries: {last_err}")
        except Exception as e:
            self.logger.error(f"❌ Failed to download video: {e}")
            raise DownloadError(f"Failed to download video: {e}")
    
    def create_clips(self, video_path: str, clips_dir: str, video_id: str, channel: str) -> List[str]:
        """Create short clips with viral-style subtitles."""
        try:
            # Initialize HighlightDetector
            highlight_detector = HighlightDetector(self.config)
            
            # Detect highlights
            highlights = highlight_detector.detect(video_path, channel)
            if not highlights:
                raise VideoProcessingError("No highlights detected in the video.")
            
            # Create clips from highlights
            clip_creator = ClipCreator(self.config)
            clips = clip_creator.create_clips(video_path, highlights, video_id, channel)
            return clips
        except Exception as e:
            raise VideoProcessingError(f"Failed to create clips: {e}")

    def _get_video_duration(self, video_path: str) -> int:
        """Get the duration of a video in seconds."""
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                capture_output=True, text=True
            )
            return int(float(result.stdout.strip()))
        except Exception as e:
            self.logger.error(f"Failed to get video duration: {e}")
            return 0

    def add_logo(self, video_path: str, output_dir: str, channel: str) -> str:
        """Add a logo overlay to the video."""
        try:
            branding = VideoBranding(self.config)
            output_path = os.path.join(output_dir, f"{Path(video_path).stem}_branded.mp4")
            return branding.add_logo(video_path, output_path, channel)
        except Exception as e:
            raise VideoProcessingError(f"Failed to add logo: {e}")