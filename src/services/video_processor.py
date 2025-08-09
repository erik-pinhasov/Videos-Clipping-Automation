"""
Video processing service that orchestrates the complete pipeline.
"""

import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.core.logger import get_logger
from src.core.exceptions import VideoProcessingError, DownloadError, UploadError
from src.services.downloader import VideoDownloader
from src.services.branding import VideoBranding
from src.services.metadata_service import MetadataService
from src.services.highlight_detector import HighlightDetector
from src.services.clip_creator import ClipCreator
from src.services.uploader import VideoUploader
import config


@dataclass
class ProcessingResult:
    """Result of video processing operation."""
    success: bool
    video_id: str
    clips_created: int = 0
    uploads_successful: int = 0
    rumble_uploaded: bool = False
    youtube_uploads: int = 0
    error: Optional[str] = None
    processing_time: float = 0.0


class VideoProcessor:
    """Orchestrates the complete video processing pipeline."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Initialize services
        self.downloader = VideoDownloader(cfg)
        self.branding = VideoBranding(cfg)
        self.metadata_service = MetadataService(cfg)
        self.highlight_detector = HighlightDetector(cfg)
        self.clip_creator = ClipCreator(cfg)
        self.uploader = VideoUploader(cfg)
    
    def initialize(self) -> bool:
        """Initialize all services and validate configuration."""
        try:
            self.logger.info("Initializing video processing services...")
            
            # Validate configuration
            if not self.config.validate():
                self.logger.error("Configuration validation failed")
                return False
            
            # Initialize uploader (contains YouTube authentication)
            if not self.uploader.initialize():
                self.logger.warning("Upload service initialization had issues")
                # Continue anyway as some uploads might still work
            
            # Create required directories
            self._ensure_directories()
            
            self.logger.info("✓ Video processor initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize video processor: {e}")
            return False
    
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        directories = [
            self.config.DOWNLOAD_DIR,
            self.config.CLIPS_DIR,
            self.config.ASSETS_DIR,
            "credentials"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def process_video(self, video_info: Dict[str, Any], channel: str) -> ProcessingResult:
        """Process a single video through the complete pipeline."""
        video_id = video_info["id"]
        title = video_info.get("title", "Unknown")
        video_url = video_info.get("url", "")
        
        start_time = time.time()
        
        try:
            self.logger.info(f"🎬 Starting processing pipeline for: {title}")
            self.logger.info(f"   Video ID: {video_id}")
            self.logger.info(f"   Channel: {channel}")
            
            # Step 1: Download video
            self.logger.info("📥 Step 1: Downloading video...")
            video_path = self._download_video(video_info)
            
            # Step 2: Add branding
            self.logger.info("🏷️ Step 2: Adding logo overlay...")
            branded_path = self._add_branding(video_path, video_id, channel)
            
            # Step 3: Generate metadata
            self.logger.info("📝 Step 3: Generating metadata...")
            metadata = self._generate_metadata(branded_path, title)
            
            # Step 4: Upload to Rumble (full video)
            rumble_success = False
            if getattr(self.config, 'ENABLE_RUMBLE_UPLOAD', True):
                self.logger.info("📤 Step 4: Uploading to Rumble...")
                rumble_success = self._upload_to_rumble(branded_path, metadata)
            else:
                self.logger.info("⏭️ Step 4: Rumble upload disabled, skipping...")
            
            # Step 5: Create highlight clips
            self.logger.info("✂️ Step 5: Creating highlight clips...")
            clips = self._create_highlights(branded_path, video_id, channel)
            
            # Step 6: Upload clips to YouTube
            youtube_uploads = 0
            if getattr(self.config, 'ENABLE_YOUTUBE_UPLOAD', True):
                self.logger.info("🎯 Step 6: Uploading clips to YouTube...")
                youtube_uploads = self._upload_clips_to_youtube(clips, video_id, metadata)
            else:
                self.logger.info("⏭️ Step 6: YouTube upload disabled, skipping...")
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            self.logger.info(f"✅ Pipeline completed successfully for {video_id}")
            self.logger.info(f"📊 Results: {len(clips)} clips created, {youtube_uploads} YouTube uploads, "
                           f"Rumble: {'✓' if rumble_success else '✗'}")
            self.logger.info(f"⏱️ Total processing time: {processing_time:.1f}s")
            
            return ProcessingResult(
                success=True,
                video_id=video_id,
                clips_created=len(clips),
                uploads_successful=youtube_uploads + (1 if rumble_success else 0),
                rumble_uploaded=rumble_success,
                youtube_uploads=youtube_uploads,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Pipeline failed for {video_id}: {str(e)}"
            self.logger.error(error_msg)
            
            return ProcessingResult(
                success=False,
                video_id=video_id,
                error=error_msg,
                processing_time=processing_time
            )
    
    def _download_video(self, video_info: Dict[str, Any]) -> str:
        """Download video and return path."""
        try:
            video_url = video_info.get("url", "")
            video_id = video_info["id"]
            
            if not video_url:
                # For mock data, create a dummy file
                self.logger.info("Mock video detected, creating dummy file...")
                dummy_path = os.path.join(self.config.DOWNLOAD_DIR, f"{video_id}.mp4")
                Path(dummy_path).touch()
                return dummy_path
            
            video_path = self.downloader.download(video_url, video_id)
            self.logger.info(f"✓ Video downloaded: {Path(video_path).name}")
            return video_path
            
        except Exception as e:
            raise DownloadError(f"Failed to download video: {e}")
    
    def _add_branding(self, video_path: str, video_id: str, channel: str) -> str:
        """Add channel logo overlay."""
        try:
            branded_path = os.path.join(self.config.DOWNLOAD_DIR, f"{video_id}_branded.mp4")
            
            # Check if it's a dummy file (mock data)
            if os.path.getsize(video_path) == 0:
                self.logger.info("Mock video detected, copying dummy file...")
                shutil.copy2(video_path, branded_path)
                return branded_path
            
            # Check if logo exists for channel
            if channel not in self.config.CHANNEL_LOGOS:
                self.logger.warning(f"No logo configuration for channel {channel}, using original video")
                shutil.copy2(video_path, branded_path)
                return branded_path
            
            logo_config = self.config.CHANNEL_LOGOS[channel]
            logo_path = logo_config['logo_path']
            
            if not os.path.exists(logo_path):
                self.logger.warning(f"Logo file not found: {logo_path}, using original video")
                shutil.copy2(video_path, branded_path)
                return branded_path
            
            # Add logo overlay
            self.branding.add_logo(video_path, branded_path, channel)
            self.logger.info("✓ Logo overlay added successfully")
            return branded_path
            
        except Exception as e:
            # Fallback: copy original video
            self.logger.warning(f"Logo overlay failed: {e}, using original video")
            branded_path = os.path.join(self.config.DOWNLOAD_DIR, f"{video_id}_branded.mp4")
            shutil.copy2(video_path, branded_path)
            return branded_path
    
    def _generate_metadata(self, video_path: str, title: str) -> Dict[str, Any]:
        """Generate metadata for the video."""
        try:
            metadata = self.metadata_service.generate(video_path, title)
            self.logger.info(f"✓ Metadata generated: '{metadata.get('title', 'No title')[:50]}...'")
            return metadata
            
        except Exception as e:
            self.logger.warning(f"Metadata generation failed: {e}, using fallback")
            return {
                "title": title[:100] if title else "Amazing Wildlife Video",
                "description": "🌿 Incredible wildlife and nature moments captured in stunning detail! 🦅✨",
                "tags": ["wildlife", "nature", "animals", "amazing", "documentary"]
            }
    
    def _upload_to_rumble(self, video_path: str, metadata: Dict[str, Any]) -> bool:
        """Upload video to Rumble."""
        try:
            success = self.uploader.upload_to_rumble(
                video_path,
                metadata["title"],
                metadata["description"], 
                metadata.get("tags", [])
            )
            
            if success:
                self.logger.info("✓ Successfully uploaded to Rumble")
                return True
            else:
                self.logger.warning("Rumble upload returned failure")
                return False
                
        except Exception as e:
            # Don't fail the entire pipeline for Rumble upload issues
            self.logger.warning(f"Rumble upload failed: {e}")
            return False
    
    def _create_highlights(self, video_path: str, video_id: str, channel: str) -> List[str]:
        """Create highlight clips."""
        try:
            # Skip for dummy/mock files
            if os.path.getsize(video_path) == 0:
                self.logger.info("Mock video detected, creating dummy clips...")
                clips = []
                for i in range(2):  # Create 2 mock clips
                    clip_path = os.path.join(self.config.CLIPS_DIR, f"{video_id}_clip_{i+1}.mp4")
                    Path(clip_path).touch()
                    clips.append(clip_path)
                return clips
            
            # Detect highlights
            highlights = self.highlight_detector.detect(video_path)
            
            if not highlights:
                self.logger.warning("No highlights detected, creating default clip")
                # Create a single default clip from the beginning
                highlights = [{
                    "start": 10,
                    "end": min(70, 300),  # 60 seconds or less
                    "score": 0.5
                }]
            
            # Create clips from highlights
            clips = self.clip_creator.create_clips(video_path, highlights, video_id, channel)
            
            self.logger.info(f"✓ Created {len(clips)} highlight clips")
            
            # Log clip details
            for i, highlight in enumerate(highlights[:len(clips)]):
                start, end = highlight["start"], highlight["end"]
                duration = end - start
                self.logger.info(f"   Clip {i+1}: {start:.1f}s → {end:.1f}s ({duration:.1f}s)")
            
            return clips
            
        except Exception as e:
            raise VideoProcessingError(f"Failed to create highlights: {e}")
    
    def _upload_clips_to_youtube(self, clips: List[str], video_id: str, base_metadata: Dict[str, Any]) -> int:
        """Upload clips to YouTube and return number of successful uploads."""
        successful = 0
        
        for i, clip_path in enumerate(clips):
            try:
                # Generate YouTube Shorts optimized metadata
                clip_metadata = self.metadata_service.generate_youtube_shorts_metadata(base_metadata)
                
                # Customize title for each clip
                clip_title = f"{clip_metadata['title']} - Part {i+1}"
                if len(clip_title) > 100:
                    clip_title = f"{base_metadata.get('title', 'Wildlife')[:80]} - Part {i+1} #Shorts"
                
                clip_metadata['title'] = clip_title
                
                # Upload to YouTube
                success = self.uploader.upload_to_youtube(clip_path, clip_metadata)
                
                if success:
                    successful += 1
                    self.logger.info(f"   ✓ Uploaded clip {i+1}/{len(clips)} to YouTube")
                else:
                    self.logger.error(f"   ✗ Failed to upload clip {i+1}")
                
                # Rate limiting between uploads
                if i < len(clips) - 1:  # Don't wait after last clip
                    time.sleep(getattr(self.config, 'UPLOAD_RATE_LIMIT_DELAY', 5))
                
            except Exception as e:
                self.logger.error(f"   ✗ Failed to upload clip {i+1}: {e}")
                # Continue with other clips
        
        self.logger.info(f"✓ YouTube uploads completed: {successful}/{len(clips)} successful")
        return successful