"""
Highlight detection service for finding interesting segments in videos.
"""

import random
from typing import Dict, Any, List
from pathlib import Path

from src.core.logger import get_logger
from src.core.exceptions import HighlightDetectionError
import config


class HighlightDetector:
    """Detects highlight segments in videos for creating clips."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Content-aware segment preferences (can be customized per channel type)
        self.segment_strategies = {
            'nature': {
                'prefer_start': True,  # Nature videos often have good intros
                'avoid_middle_cuts': True,  # Avoid cutting in middle of scenes
                'min_scene_length': 20  # Nature scenes need time to develop
            },
            'wildlife': {
                'prefer_action': True,  # Wildlife videos have action moments
                'avoid_start': False,  # Can start anywhere
                'dynamic_length': True  # Vary clip lengths based on content
            },
            'scenic': {
                'prefer_continuous': True,  # Scenic content flows better continuously  
                'longer_clips': True,  # Scenic content works better with longer clips
                'smooth_transitions': True
            },
            'educational': {
                'prefer_complete_segments': True,  # Don't cut off explanations
                'avoid_mid_sentence': True,
                'prefer_beginning': True
            },
            'default': {
                'balanced_approach': True,
                'standard_lengths': True
            }
        }
    
    def detect(self, video_path: str, channel: str = None) -> List[Dict[str, Any]]:
        """
        Detect highlight segments in video.
        
        Args:
            video_path: Path to video file
            channel: Channel name for content-aware detection
            
        Returns:
            List of highlight dictionaries with 'start' and 'end' times
        """
        try:
            # Get video duration
            video_duration = self._get_video_duration(video_path)
            
            if video_duration < self.config.CLIP_DURATION_MIN:
                self.logger.warning(f"Video too short for clips: {video_duration}s")
                return []
            
            # Get content category and strategy
            category = self.config.get_channel_category(channel) if channel else 'default'
            strategy = self.segment_strategies.get(category, self.segment_strategies['default'])
            
            self.logger.info(f"Using '{category}' detection strategy for highlight extraction")
            
            # Generate highlights based on strategy
            highlights = self._generate_highlights_with_strategy(video_duration, strategy)
            
            self.logger.info(f"Detected {len(highlights)} highlight segments using {category} strategy")
            for i, highlight in enumerate(highlights):
                duration = highlight['end'] - highlight['start']
                self.logger.debug(f"  Segment {i+1}: {highlight['start']:.1f}s → {highlight['end']:.1f}s ({duration:.1f}s)")
            
            return highlights
            
        except Exception as e:
            self.logger.error(f"Highlight detection failed: {e}")
            raise HighlightDetectionError(f"Failed to detect highlights: {e}")
    
    def _generate_highlights_with_strategy(self, video_duration: int, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate highlights based on content strategy."""
        highlights = []
        max_clips = min(self.config.MAX_CLIPS_PER_VIDEO, 3)
        
        # Adjust clip durations based on strategy
        if strategy.get('longer_clips'):
            min_duration = max(self.config.CLIP_DURATION_MIN, 30)
            max_duration = min(self.config.CLIP_DURATION_MAX, 90)
        else:
            min_duration = self.config.CLIP_DURATION_MIN
            max_duration = self.config.CLIP_DURATION_MAX
        
        # Generate segments based on strategy
        if strategy.get('prefer_continuous'):
            highlights = self._generate_continuous_segments(video_duration, max_clips, min_duration, max_duration)
        elif strategy.get('prefer_start'):
            highlights = self._generate_start_focused_segments(video_duration, max_clips, min_duration, max_duration)
        elif strategy.get('prefer_action'):
            highlights = self._generate_action_focused_segments(video_duration, max_clips, min_duration, max_duration)
        else:
            highlights = self._generate_balanced_segments(video_duration, max_clips, min_duration, max_duration)
        
        return highlights
    
    def _generate_continuous_segments(self, video_duration: int, max_clips: int, 
                                    min_duration: int, max_duration: int) -> List[Dict[str, Any]]:
        """Generate continuous, flowing segments (good for scenic content)."""
        highlights = []
        
        # Create fewer, longer segments that flow together
        segment_count = min(max_clips, 2)  # Prefer fewer segments for continuity
        
        for i in range(segment_count):
            # Distribute segments evenly across video
            segment_start = int((video_duration / segment_count) * i)
            
            # Ensure we don't start too late
            latest_start = video_duration - max_duration - 10
            segment_start = min(segment_start, latest_start)
            segment_start = max(segment_start, 5)  # At least 5s in
            
            # Use longer durations for scenic content
            duration = random.randint(max_duration - 15, max_duration)
            segment_end = min(segment_start + duration, video_duration - 5)
            
            if segment_end - segment_start >= min_duration:
                highlights.append({
                    'start': segment_start,
                    'end': segment_end,
                    'score': 0.85,  # High confidence for scenic content
                    'type': 'continuous'
                })
        
        return highlights
    
    def _generate_start_focused_segments(self, video_duration: int, max_clips: int,
                                       min_duration: int, max_duration: int) -> List[Dict[str, Any]]:
        """Generate segments focusing on video start (good for nature intros)."""
        highlights = []
        
        # First segment from the beginning
        first_duration = random.randint(min_duration + 10, max_duration)
        first_end = min(first_duration + 10, video_duration // 3)  # Don't take more than 1/3
        
        highlights.append({
            'start': 5,  # Skip first few seconds
            'end': first_end,
            'score': 0.9,  # High confidence for start
            'type': 'intro'
        })
        
        # Add 1-2 more segments from middle/end
        remaining_clips = min(max_clips - 1, 2)
        for i in range(remaining_clips):
            # Place in latter 2/3 of video
            start_range_begin = video_duration // 3
            start_range_end = video_duration - max_duration - 10
            
            if start_range_end > start_range_begin:
                segment_start = random.randint(start_range_begin, start_range_end)
                duration = random.randint(min_duration, max_duration - 10)
                segment_end = segment_start + duration
                
                # Check for overlap with existing segments
                overlap = any(not (segment_end <= h['start'] or segment_start >= h['end']) 
                            for h in highlights)
                
                if not overlap:
                    highlights.append({
                        'start': segment_start,
                        'end': segment_end,
                        'score': 0.75,
                        'type': 'supporting'
                    })
        
        return highlights
    
    def _generate_action_focused_segments(self, video_duration: int, max_clips: int,
                                        min_duration: int, max_duration: int) -> List[Dict[str, Any]]:
        """Generate segments focusing on dynamic moments (good for wildlife)."""
        highlights = []
        
        # For action content, prefer multiple shorter segments
        for i in range(max_clips):
            # Use shorter durations for action content
            duration = random.randint(min_duration, min(max_duration - 10, 45))
            
            # Place randomly but avoid very start/end
            earliest_start = 15
            latest_start = video_duration - duration - 15
            
            if latest_start > earliest_start:
                segment_start = random.randint(earliest_start, latest_start)
                segment_end = segment_start + duration
                
                # Check for overlap
                overlap = any(not (segment_end <= h['start'] or segment_start >= h['end']) 
                            for h in highlights)
                
                if not overlap:
                    highlights.append({
                        'start': segment_start,
                        'end': segment_end,
                        'score': random.uniform(0.7, 0.9),
                        'type': 'action'
                    })
        
        return highlights
    
    def _generate_balanced_segments(self, video_duration: int, max_clips: int,
                                  min_duration: int, max_duration: int) -> List[Dict[str, Any]]:
        """Generate balanced segments (default strategy)."""
        highlights = []
        
        for i in range(max_clips):
            duration = random.randint(min_duration, max_duration)
            
            # Ensure we don't go past video end
            max_start = max(5, video_duration - duration - 5)
            
            if max_start <= 5:
                break
            
            segment_start = random.randint(5, max_start)
            segment_end = segment_start + duration
            
            # Check for overlap
            overlap = any(not (segment_end <= h['start'] or segment_start >= h['end']) 
                        for h in highlights)
            
            if not overlap:
                highlights.append({
                    'start': segment_start,
                    'end': segment_end,
                    'score': random.uniform(0.7, 0.85),
                    'type': 'balanced'
                })
        
        return sorted(highlights, key=lambda x: x['start'])
    
    def _get_video_duration(self, video_path: str) -> int:
        """Get video duration in seconds."""
        try:
            import subprocess
            result = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return int(float(result.stdout.strip()))
            else:
                # Fallback: estimate from file size
                file_size_mb = Path(video_path).stat().st_size / (1024 * 1024)
                estimated_duration = int(file_size_mb * 8)  # Rough estimate
                self.logger.warning(f"Could not get exact duration, estimating: {estimated_duration}s")
                return estimated_duration
                
        except Exception as e:
            self.logger.warning(f"Duration detection failed: {e}, using default")
            return 300  # 5 minutes default