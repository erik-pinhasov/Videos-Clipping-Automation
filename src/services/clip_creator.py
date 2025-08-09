"""
Clip creation service for extracting highlight segments from videos.
"""

import os
import subprocess
from typing import List, Dict, Any
from pathlib import Path

from src.core.logger import get_logger
from src.core.exceptions import ClipCreationError
import config


class ClipCreator:
    """Creates video clips from highlight segments."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
    
    def create_clips(self, video_path: str, highlights: List[Dict[str, Any]], 
                     video_id: str, channel: str) -> List[str]:
        """
        Create video clips from highlight segments.
        
        Args:
            video_path: Path to source video
            highlights: List of highlight dictionaries with start/end times
            video_id: Video ID for naming clips
            channel: Channel name
            
        Returns:
            List of paths to created clip files
        """
        try:
            if not highlights:
                self.logger.warning("No highlights provided for clip creation")
                return []
            
            # Ensure clips directory exists
            Path(self.config.CLIPS_DIR).mkdir(exist_ok=True)
            
            created_clips = []
            
            for i, highlight in enumerate(highlights):
                clip_filename = f"{video_id}_clip_{i+1}.mp4"
                clip_path = os.path.join(self.config.CLIPS_DIR, clip_filename)
                
                start_time = highlight['start']
                duration = highlight['end'] - highlight['start']
                
                try:
                    # Create clip using FFmpeg
                    success = self._extract_clip(
                        video_path, clip_path, start_time, duration
                    )
                    
                    if success:
                        created_clips.append(clip_path)
                        self.logger.info(f"  ✓ Created clip {i+1}: {clip_filename}")
                    else:
                        self.logger.error(f"  ✗ Failed to create clip {i+1}")
                        
                except Exception as e:
                    self.logger.error(f"  ✗ Error creating clip {i+1}: {e}")
                    continue
            
            self.logger.info(f"Successfully created {len(created_clips)} clips")
            return created_clips
            
        except Exception as e:
            self.logger.error(f"Clip creation failed: {e}")
            raise ClipCreationError(f"Failed to create clips: {e}")
    
    def _extract_clip(self, input_video: str, output_clip: str, 
                     start_time: float, duration: float) -> bool:
        """Extract a single clip using FFmpeg."""
        try:
            cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-i', input_video,
                '-ss', str(start_time),  # Start time
                '-t', str(duration),     # Duration
                '-c:v', 'libx264',       # Video codec
                '-c:a', 'aac',           # Audio codec
                '-preset', 'medium',      # Encoding preset
                '-crf', '23',            # Quality
                '-movflags', '+faststart', # Web optimization
                output_clip
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per clip
            )
            
            if result.returncode == 0 and os.path.exists(output_clip):
                return True
            else:
                self.logger.error(f"FFmpeg error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Clip extraction timed out")
            return False
        except Exception as e:
            self.logger.error(f"Clip extraction failed: {e}")
            return False
    
    def add_subtitles_to_clip(self, clip_path: str, subtitle_text: str) -> bool:
        """Add hardcoded subtitles to clip for YouTube Shorts."""
        try:
            # This is a placeholder for subtitle functionality
            # In a full implementation, this would generate subtitle files
            # and burn them into the video using FFmpeg
            self.logger.debug(f"Adding subtitles to {clip_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add subtitles: {e}")
            return False