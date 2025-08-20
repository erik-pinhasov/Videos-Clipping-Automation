import os
import glob
from pathlib import Path
from typing import List, Optional

from src.core.logger import get_logger
import config


class ResourceCleaner:
    """Handles cleanup of temporary files and resources."""
    
    def __init__(self):
        self.config = config.Config()
        self.logger = get_logger(__name__)
    
    def cleanup_video_files(self, video_id: str) -> None:
        """Clean up all temporary files for a specific video."""
        try:
            files_cleaned = []
            
            # Clean download directory
            download_patterns = [
                f"{self.config.DOWNLOAD_DIR}/{video_id}*",
                f"{self.config.DOWNLOAD_DIR}/*{video_id}*"
            ]
            
            for pattern in download_patterns:
                files = glob.glob(pattern)
                for file_path in files:
                    try:
                        os.remove(file_path)
                        files_cleaned.append(file_path)
                    except OSError as e:
                        self.logger.warning(f"Could not remove {file_path}: {e}")
            
            # Clean clips directory
            clips_pattern = f"{config.CLIPS_DIR}/{video_id}_*"
            clip_files = glob.glob(clips_pattern)
            
            for clip_path in clip_files:
                try:
                    os.remove(clip_path)
                    files_cleaned.append(clip_path)
                except OSError as e:
                    self.logger.warning(f"Could not remove {clip_path}: {e}")
            
            # Clean audio directory
            audio_pattern = f"{config.AUDIO_DIR}/{video_id}*"
            audio_files = glob.glob(audio_pattern)
            
            for audio_path in audio_files:
                try:
                    os.remove(audio_path)
                    files_cleaned.append(audio_path)
                except OSError as e:
                    self.logger.warning(f"Could not remove {audio_path}: {e}")
            
            if files_cleaned:
                self.logger.info(f"Cleaned up {len(files_cleaned)} files for video {video_id}")
                for file_path in files_cleaned:
                    self.logger.debug(f"  Removed: {Path(file_path).name}")
            else:
                self.logger.debug(f"No files to clean for video {video_id}")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up video files: {e}")
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> None:
        """Clean up old temporary files across all directories."""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (max_age_hours * 3600)
            
            directories = [
                self.config.DOWNLOAD_DIR,
                self.config.CLIPS_DIR,
                self.config.AUDIO_DIR
            ]
            
            total_cleaned = 0
            
            for directory in directories:
                if not os.path.exists(directory):
                    continue
                
                for file_path in glob.glob(os.path.join(directory, "*")):
                    try:
                        if os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            total_cleaned += 1
                            self.logger.debug(f"Removed old file: {file_path}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove old file {file_path}: {e}")
            
            if total_cleaned > 0:
                self.logger.info(f"Cleaned up {total_cleaned} old files (>{max_age_hours}h old)")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old files: {e}")
    
    def ensure_directories(self, directories: List[str]) -> None:
        """Ensure required directories exist."""
        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                self.logger.debug(f"Directory ensured: {directory}")
            except Exception as e:
                self.logger.error(f"Could not create directory {directory}: {e}")
    
    def get_directory_size(self, directory: str) -> Optional[float]:
        """Get total size of directory in MB."""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        pass
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return None
    
    def cleanup_by_size_limit(self, directory: str, max_size_mb: float) -> None:
        """Clean up oldest files if directory exceeds size limit."""
        try:
            current_size = self.get_directory_size(directory)
            if current_size is None or current_size <= max_size_mb:
                return
            
            # Get all files with modification times
            files_with_times = []
            for file_path in glob.glob(os.path.join(directory, "*")):
                try:
                    mtime = os.path.getmtime(file_path)
                    size = os.path.getsize(file_path) / (1024 * 1024)
                    files_with_times.append((file_path, mtime, size))
                except OSError:
                    continue
            
            # Sort by modification time (oldest first)
            files_with_times.sort(key=lambda x: x[1])
            
            # Remove oldest files until under size limit
            for file_path, mtime, size in files_with_times:
                try:
                    os.remove(file_path)
                    current_size -= size
                    self.logger.debug(f"Removed file to free space: {file_path}")
                    
                    if current_size <= max_size_mb:
                        break
                except OSError as e:
                    self.logger.warning(f"Could not remove {file_path}: {e}")
            
            self.logger.info(f"Directory {directory} cleaned to {current_size:.1f}MB")
            
        except Exception as e:
            self.logger.error(f"Error cleaning directory by size: {e}")