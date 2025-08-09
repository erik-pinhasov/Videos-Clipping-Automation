"""
Video branding service for adding logo overlays to videos.
"""

import os
import subprocess
from typing import Dict, Any
from pathlib import Path

from src.core.logger import get_logger
from src.core.exceptions import BrandingError
import config


class VideoBranding:
    """Handles adding logo overlays to videos using FFmpeg."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
    
    def add_logo(self, input_video: str, output_video: str, channel: str) -> str:
        """
        Add channel logo overlay to video.
        
        Args:
            input_video: Path to input video
            output_video: Path for output video
            channel: Channel name to get logo settings
            
        Returns:
            str: Path to output video with logo
        """
        try:
            # Get channel logo configuration
            if channel not in self.config.CHANNEL_LOGOS:
                self.logger.warning(f"No logo config for channel {channel}, skipping overlay")
                # Copy original file
                import shutil
                shutil.copy2(input_video, output_video)
                return output_video
            
            logo_config = self.config.CHANNEL_LOGOS[channel]
            logo_path = logo_config['logo_path']
            
            if not os.path.exists(logo_path):
                self.logger.warning(f"Logo file not found: {logo_path}, skipping overlay")
                import shutil
                shutil.copy2(input_video, output_video)
                return output_video
            
            # Build FFmpeg filter for logo overlay
            overlay_filter = self._build_overlay_filter(logo_config)
            
            # FFmpeg command for adding logo
            cmd = [
                'ffmpeg', '-y',  # Overwrite output file
                '-i', input_video,  # Input video
                '-i', logo_path,    # Logo image
                '-filter_complex', overlay_filter,
                '-c:a', 'copy',     # Copy audio without re-encoding
                '-c:v', 'libx264',  # Video codec
                '-preset', 'medium', # Encoding preset
                output_video
            ]
            
            self.logger.info(f"Adding logo overlay for channel: {channel}")
            
            # Run FFmpeg command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise BrandingError(f"FFmpeg failed: {result.stderr}")
            
            if os.path.exists(output_video):
                self.logger.info(f"✓ Logo overlay added: {Path(output_video).name}")
                return output_video
            else:
                raise BrandingError("Output video file was not created")
                
        except subprocess.TimeoutExpired:
            raise BrandingError("Logo overlay operation timed out")
        except Exception as e:
            self.logger.error(f"Logo overlay failed: {e}")
            raise BrandingError(f"Failed to add logo overlay: {e}")
    
    def _build_overlay_filter(self, logo_config: Dict[str, Any]) -> str:
        """Build FFmpeg overlay filter based on logo configuration."""
        location = logo_config.get('location', 'top_left')
        spacing_x = logo_config.get('spacing_x', 10)
        spacing_y = logo_config.get('spacing_y', 10)
        
        # Position mappings
        positions = {
            'top_left': f'{spacing_x}:{spacing_y}',
            'top_right': f'W-w-{spacing_x}:{spacing_y}',
            'bottom_left': f'{spacing_x}:H-h-{spacing_y}',
            'bottom_right': f'W-w-{spacing_x}:H-h-{spacing_y}',
            'center': '(W-w)/2:(H-h)/2'
        }
        
        position = positions.get(location, positions['top_left'])
        
        # Scale logo to reasonable size (max 15% of video width)
        return f'[1:v]scale=iw*min(1\\,min(150/iw\\,150/ih)):ih*min(1\\,min(150/iw\\,150/ih))[logo];[0:v][logo]overlay={position}'