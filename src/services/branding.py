import subprocess
import config
from src.core.logger import get_logger
from src.core.exceptions import BrandingError


class VideoBranding:
    """Handles adaptive logo overlay with resolution scaling."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)

    def add_logo(self, input_path: str, output_path: str, channel: str) -> str:
        """Add a logo overlay fast (QSV ICQ when available) with source-like quality."""
        import os, subprocess

        # --- Read channel-specific placement ---
        channel_config = self.config.CHANNEL_LOGOS.get(channel)
        if not channel_config:
            raise BrandingError(f"No logo configuration found for channel: {channel}")

        logo_path = channel_config['logo_path']
        location  = channel_config['location']
        spacing_x = int(channel_config['spacing_x'])
        spacing_y = int(channel_config['spacing_y'])

        # Build overlay position (add format=auto for robustness)
        if location == 'top_left':
            position = f"overlay={spacing_x}:{spacing_y}:format=auto"
        elif location == 'top_right':
            position = f"overlay=W-w-{spacing_x}:{spacing_y}:format=auto"
        elif location == 'bottom_left':
            position = f"overlay={spacing_x}:H-h-{spacing_y}:format=auto"
        elif location == 'bottom_right':
            position = f"overlay=W-w-{spacing_x}:H-h-{spacing_y}:format=auto"
        else:
            raise BrandingError(f"Invalid logo location: {location}")

        self.logger.info(f"Using logo: {logo_path}")
        self.logger.info(f"Logo position: {position}")

        # Always use CPU libx264 encoder for AMD hardware
        ext = os.path.splitext(output_path)[1].lower()
        writing_mp4 = ext in (".mp4", ".m4v", ".mov")
        acodec = ["-c:a", "aac", "-b:a", "160k"] if writing_mp4 else ["-c:a", "copy"]
        mp4flags = ["-movflags", "+faststart"] if writing_mp4 else []
        self.logger.info("Encoder: libx264 (CRF 28, medium preset)")
        vcodec = ["-c:v", "libx264", "-crf", "28", "-preset", "medium", "-pix_fmt", "yuv420p"]

        # --- Build and run ffmpeg ---
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", input_path, "-i", logo_path,
            "-filter_complex", position,
            *vcodec, *acodec, *mp4flags,
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.error(f"FFmpeg error: {result.stderr}")
            raise BrandingError(f"Failed to add logo: {result.stderr}")

        # Optional size sanity note
        try:
            in_sz = os.path.getsize(input_path)
            out_sz = os.path.getsize(output_path)
            # If output grows unexpectedly, log a warning for user awareness
            if out_sz > in_sz * 1.5:
                self.logger.warning("Output grew >50%. For smaller files, try adjusting CRF or preset.")
        except Exception:
            pass

        self.logger.info(f"Logo added successfully: {output_path}")
        return output_path
