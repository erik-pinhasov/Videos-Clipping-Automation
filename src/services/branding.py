"""
Adaptive logo branding with resolution scaling and aspect ratio preservation.
"""

import os
import subprocess
from pathlib import Path
from typing import Tuple, Dict, Any
import config
from src.core.logger import get_logger
from src.core.exceptions import BrandingError


class VideoBranding:
    """Handles adaptive logo overlay with resolution scaling."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Base configuration for 4K (3840x2160)
        self.base_resolution = (3840, 2160)
        
        # Original logo sizes for each channel
        self.logo_sizes = {
            'naturesmomentstv': (530, 530),
            'navwildanimaldocumentary': (900, 260),
            'ScenicScenes': (1230, 170),
            'wildnatureus2024': (670, 350)
        }
        
    def add_logo(self, input_path: str, output_path: str, channel: str) -> str:
        """Add channel logo with adaptive positioning and scaling."""
        try:
            self.logger.info(f"Adding logo overlay for channel: {channel}")
            
            # Get channel configuration
            channel_config = self.config.CHANNEL_LOGOS.get(channel)
            if not channel_config:
                raise BrandingError(f"No configuration found for channel: {channel}")
            
            logo_path = channel_config.get('logo_path')
            if not logo_path or not Path(logo_path).exists():
                raise BrandingError(f"Logo file not found: {logo_path}")
            
            # Get video resolution
            video_width, video_height = self._get_video_resolution(input_path)
            
            # Calculate adaptive positioning and scaling
            scaled_config = self._calculate_adaptive_scaling(
                channel, video_width, video_height, channel_config
            )
            
            # Apply logo overlay
            success = self._apply_logo_overlay(
                input_path, output_path, logo_path, scaled_config
            )
            
            if success:
                file_size = Path(output_path).stat().st_size / (1024 * 1024)
                self.logger.info(f"✓ Logo overlay completed ({file_size:.1f} MB)")
                return output_path
            else:
                raise BrandingError("Logo overlay failed")
                
        except Exception as e:
            self.logger.error(f"Logo branding failed: {e}")
            # Return original path as fallback
            if input_path != output_path and Path(input_path).exists():
                import shutil
                shutil.copy2(input_path, output_path)
            return output_path
    
    def _get_video_resolution(self, video_path: str) -> Tuple[int, int]:
        """Get actual video resolution."""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width')
                        height = stream.get('height')
                        if width and height:
                            return (width, height)
            
            # Fallback to default
            return (1920, 1080)
            
        except Exception as e:
            self.logger.warning(f"Could not determine video resolution: {e}")
            return (1920, 1080)
    
    def _calculate_adaptive_scaling(self, channel: str, video_width: int, 
                                  video_height: int, channel_config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate adaptive logo positioning and scaling."""
        
        # Get original values (designed for 3840x2160)
        original_x = channel_config.get('x', 0)
        original_y = channel_config.get('y', 0)
        original_logo_size = self.logo_sizes.get(channel, (200, 200))
        
        # Calculate scale factors
        width_scale = video_width / self.base_resolution[0]
        height_scale = video_height / self.base_resolution[1]
        
        # Use uniform scaling to maintain aspect ratios
        # Choose the smaller scale to ensure logo fits
        uniform_scale = min(width_scale, height_scale)
        
        # Calculate new position (maintain relative position)
        new_x = int(original_x * width_scale)
        new_y = int(original_y * height_scale)
        
        # Calculate new logo size (maintain aspect ratio)
        new_logo_width = int(original_logo_size[0] * uniform_scale)
        new_logo_height = int(original_logo_size[1] * uniform_scale)
        
        # Ensure logo doesn't exceed video boundaries
        max_x = video_width - new_logo_width - 10  # 10px padding
        max_y = video_height - new_logo_height - 10  # 10px padding
        
        new_x = max(0, min(new_x, max_x))
        new_y = max(0, min(new_y, max_y))
        
        scaled_config = {
            'x': new_x,
            'y': new_y,
            'logo_width': new_logo_width,
            'logo_height': new_logo_height,
            'video_width': video_width,
            'video_height': video_height,
            'scale_factor': uniform_scale
        }
        
        self.logger.info(f"  Video resolution: {video_width}x{video_height}")
        self.logger.info(f"  Scale factor: {uniform_scale:.3f}")
        self.logger.info(f"  Logo position: ({new_x}, {new_y})")
        self.logger.info(f"  Logo size: {new_logo_width}x{new_logo_height}")
        
        return scaled_config
    
    def _apply_logo_overlay(self, input_path: str, output_path: str, 
                           logo_path: str, scaled_config: Dict[str, Any]) -> bool:
        """Apply the logo overlay using ffmpeg."""
        try:
            # Build ffmpeg command with adaptive scaling
            cmd = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-i', logo_path,
                '-filter_complex',
                f'[1:v]scale={scaled_config["logo_width"]}:{scaled_config["logo_height"]}[logo];'
                f'[0:v][logo]overlay={scaled_config["x"]}:{scaled_config["y"]}',
                '-c:a', 'copy',  # Copy audio without re-encoding
                '-preset', 'medium',  # Balance between speed and quality
                '-crf', '18',  # High quality
                output_path
            ]
            
            self.logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            # Execute with progress tracking
            import time
            start_time = time.time()
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=600  # 10 minute timeout
            )
            
            processing_time = time.time() - start_time
            
            if result.returncode == 0 and Path(output_path).exists():
                self.logger.info(f"✓ Logo overlay completed in {processing_time:.1f}s")
                return True
            else:
                self.logger.error(f"FFmpeg error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Logo overlay timed out after 10 minutes")
            return False
        except Exception as e:
            self.logger.error(f"Logo overlay error: {e}")
            return False