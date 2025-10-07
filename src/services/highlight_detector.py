"""
Intelligent highlight detection using Hugging Face models and local analysis.
"""

import os
import json
import numpy as np
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
import requests
from datetime import datetime
import config
from src.core.logger import get_logger
from src.core.exceptions import HighlightDetectionError


class HighlightDetector:
    """Detects video highlights using multiple strategies and HF models."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Detection strategies per channel
        self.detection_strategies = {
            'naturesmomentstv': 'nature_documentary',
            'navwildanimaldocumentary': 'wildlife_action',
            'wildnatureus2024': 'scenic_nature',
            'ScenicScenes': 'scenic'
        }
        
        # No HF usage anymore; rely on local analysis only
    
    def detect(self, video_path: str, channel: str) -> List[Dict[str, Any]]:
        """Detect highlights using intelligent analysis."""
        try:
            strategy = self.detection_strategies.get(channel, 'nature_documentary')
            self.logger.info(f"Using '{strategy}' detection strategy for highlight extraction")
            
            # Get video info first
            video_duration = self._get_video_duration(video_path)
            if video_duration < 60:  # Too short
                return []
            
            # Use multiple detection methods
            highlights = []
            
            # Method 1: Local audio analysis (free, unlimited)
            audio_highlights = self._detect_audio_peaks(video_path, strategy)
            highlights.extend(audio_highlights)
            
            # Method 2: Local motion analysis (free, unlimited)  
            motion_highlights = self._detect_motion_peaks(video_path, strategy)
            highlights.extend(motion_highlights)
            
            # Method 3 removed: HF-powered content analysis is disabled
            
            # Process and rank highlights
            final_highlights = self._process_highlights(highlights, video_duration, strategy)
            
            self.logger.info(f"Detected {len(final_highlights)} highlight segments using {strategy} strategy")
            
            return final_highlights
            
        except Exception as e:
            self.logger.error(f"Highlight detection failed: {e}")
            # Return basic highlights as fallback
            return self._create_fallback_highlights(video_path)
    
    def _detect_audio_peaks(self, video_path: str, strategy: str) -> List[Dict[str, Any]]:
        """Detect audio-based highlights using local analysis."""
        try:
            # Extract audio features using ffmpeg
            cmd = [
                'ffmpeg', '-i', video_path, '-af',
                'volumedetect,astats=metadata=1:reset=1:length=5',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Parse audio analysis (simplified for now)
            highlights = []
            
            # Strategy-specific audio detection
            if strategy in ['wildlife_action', 'nature_documentary']:
                # Look for sudden audio changes (animal calls, movements)
                highlights = self._parse_audio_activity(result.stderr)
            elif strategy == 'scenic':
                # For scenic content, look for calm periods with ambient sounds
                highlights = self._parse_ambient_audio(result.stderr)
            
            return highlights
            
        except Exception as e:
            self.logger.debug(f"Audio peak detection failed: {e}")
            return []
    
    def _detect_motion_peaks(self, video_path: str, strategy: str) -> List[Dict[str, Any]]:
        """Detect motion-based highlights using local analysis."""
        try:
            # Use ffmpeg to detect motion
            cmd = [
                'ffmpeg', '-i', video_path, '-vf',
                'select=gt(scene\\,0.3),showinfo',
                '-f', 'null', '-'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Parse scene changes and motion
            highlights = []
            
            # Extract timestamps from ffmpeg output
            for line in result.stderr.split('\n'):
                if 'pts_time:' in line:
                    try:
                        timestamp = float(line.split('pts_time:')[1].split()[0])
                        
                        highlights.append({
                            'start': max(0, timestamp - 30),  # 30s before peak
                            'end': timestamp + 30,            # 30s after peak
                            'score': 0.7,
                            'type': 'motion',
                            'reason': 'Scene change detected'
                        })
                    except (ValueError, IndexError):
                        continue
            
            return highlights[:60]  # Allow more motion peaks for long videos
            
        except Exception as e:
            self.logger.debug(f"Motion peak detection failed: {e}")
            return []
    
    # Removed: _detect_content_highlights (HF models)
    
    def _extract_keyframes(self, video_path: str, max_frames: int = 10) -> List[Dict[str, Any]]:
        """Extract keyframes for HF analysis."""
        try:
            duration = self._get_video_duration(video_path)
            
            # Get evenly spaced timestamps
            timestamps = []
            interval = max(60, duration // max_frames)  # Adjust interval based on video length
            for i in range(0, int(duration), interval):
                timestamps.append(i)
            
            frames = []
            for timestamp in timestamps:
                try:
                    # Extract frame as base64 for HF API
                    cmd = [
                        'ffmpeg', '-ss', str(timestamp), '-i', video_path,
                        '-vframes', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, timeout=30)
                    
                    if result.returncode == 0:
                        import base64
                        image_data = base64.b64encode(result.stdout).decode()
                        
                        frames.append({
                            'timestamp': timestamp,
                            'image_data': image_data
                        })
                        
                except Exception as e:
                    self.logger.debug(f"Frame extraction failed at {timestamp}s: {e}")
                    continue
            
            return frames
            
        except Exception as e:
            self.logger.debug(f"Keyframe extraction failed: {e}")
            return []
    
    # Removed: _query_hf_model
    
    # Removed: _is_interesting_scene (HF analysis helper)
    
    def _process_highlights(self, raw_highlights: List[Dict[str, Any]], 
                          video_duration: float, strategy: str) -> List[Dict[str, Any]]:
        """Process, merge, and rank highlights."""
        try:
            if not raw_highlights:
                return self._create_fallback_highlights_with_duration(video_duration)
            
            # Remove duplicates and overlaps
            merged_highlights = self._merge_overlapping_highlights(raw_highlights)
            
            # Ensure highlights are within video bounds
            valid_highlights = []
            for highlight in merged_highlights:
                start = max(0, highlight['start'])
                end = min(video_duration - 5, highlight['end'])  # Leave 5s buffer
                
                # Ensure minimum clip length (we can extend short ones later during clip creation)
                if end - start >= 20:  # At least 20 seconds
                    # Adjust for optimal short-form length (45-60s)
                    if end - start > 60:
                        end = start + 55  # Optimal shorts length
                    
                    valid_highlights.append({
                        'start': start,
                        'end': end,
                        'score': highlight.get('score', 0.5),
                        'type': highlight.get('type', 'unknown'),
                        'reason': highlight.get('reason', 'Highlight detected')
                    })
            
            # Sort by score (best first)
            valid_highlights.sort(key=lambda x: x['score'], reverse=True)
            
            # Determine desired number of clips based on duration (~1 every 2 minutes)
            desired_max = min(100, max(8, int(video_duration / 120)))

            # If we don't have enough detected highlights, top up with evenly spaced fallbacks
            if len(valid_highlights) < desired_max:
                needed = desired_max - len(valid_highlights)
                fallback = self._generate_evenly_spaced_highlights(video_duration, length=55, stride=120)

                # Avoid heavy overlap with existing highlights (>= 15s overlap)
                def overlaps(a, b):
                    return not (a['end'] <= b['start'] + 5 or b['end'] <= a['start'] + 5)

                selected = []
                existing = valid_highlights.copy()
                for h in fallback:
                    too_close = any(overlaps(h, e) for e in existing)
                    if not too_close:
                        selected.append(h)
                        existing.append(h)
                    if len(selected) >= needed:
                        break

                valid_highlights.extend(selected)

            # Now cap to desired_max, ordering by score then start time
            valid_highlights.sort(key=lambda x: (-x.get('score', 0), x['start']))
            final_highlights = valid_highlights[:desired_max]
            
            self.logger.info(f"Processed highlights: {len(raw_highlights)} → {len(final_highlights)} final clips")
            
            return final_highlights
            
        except Exception as e:
            self.logger.error(f"Highlight processing failed: {e}")
            return self._create_fallback_highlights_with_duration(video_duration)

    def _generate_evenly_spaced_highlights(self, duration: float, length: int = 55, stride: int = 120) -> List[Dict[str, Any]]:
        """Generate evenly spaced highlight windows across the video duration."""
        highlights = []
        if duration <= 0:
            return highlights
        start_time = 10  # small buffer at the beginning
        last_start = max(10, duration - length - 5)
        t = start_time
        while t <= last_start:
            highlights.append({
                'start': t,
                'end': t + length,
                'score': 0.4,
                'type': 'fallback',
                'reason': 'Evenly spaced fallback'
            })
            t += stride
        return highlights
    
    def _merge_overlapping_highlights(self, highlights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge overlapping highlight segments."""
        if not highlights:
            return []
        
        # Sort by start time
        sorted_highlights = sorted(highlights, key=lambda x: x['start'])
        merged = [sorted_highlights[0]]
        
        for current in sorted_highlights[1:]:
            last_merged = merged[-1]
            
            # Check for overlap (with 10s buffer)
            if current['start'] <= last_merged['end'] + 10:
                # Merge highlights
                merged[-1] = {
                    'start': last_merged['start'],
                    'end': max(last_merged['end'], current['end']),
                    'score': max(last_merged['score'], current['score']),
                    'type': 'merged',
                    'reason': f"{last_merged.get('reason', '')} + {current.get('reason', '')}"
                }
            else:
                merged.append(current)
        
        return merged
    
    def _create_fallback_highlights(self, video_path: str) -> List[Dict[str, Any]]:
        """Create fallback highlights when detection fails."""
        duration = self._get_video_duration(video_path)
        return self._create_fallback_highlights_with_duration(duration)
    
    def _create_fallback_highlights_with_duration(self, duration: float) -> List[Dict[str, Any]]:
        """Create evenly spaced fallback highlights."""
        highlights = []
        
        if duration < 120:  # Less than 2 minutes
            highlights.append({
                'start': 10,
                'end': min(duration - 5, 65),
                'score': 0.5,
                'type': 'fallback',
                'reason': 'Default highlight for short video'
            })
        elif duration < 600:  # Less than 10 minutes
            # Create 2 highlights
            highlights.extend([
                {
                    'start': 30,
                    'end': 85,
                    'score': 0.6,
                    'type': 'fallback',
                    'reason': 'Early highlight'
                },
                {
                    'start': duration / 2,
                    'end': duration / 2 + 55,
                    'score': 0.6,
                    'type': 'fallback',
                    'reason': 'Mid-video highlight'
                }
            ])
        else:  # 10+ minutes
            # Create many evenly spaced highlights (~every 2 minutes)
            highlights = self._generate_evenly_spaced_highlights(duration, length=55, stride=120)
        
        return highlights
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data['format']['duration'])
            
            return 600.0  # Default fallback
            
        except Exception:
            return 600.0
    
    def _parse_audio_activity(self, stderr_output: str) -> List[Dict[str, Any]]:
        """Parse audio activity from ffmpeg output (simplified)."""
        # This is a simplified implementation
        # In production, you'd parse actual volume levels and peaks
        highlights = []
        
        # Mock implementation - return some basic highlights
        highlights.append({
            'start': 60,
            'end': 115,
            'score': 0.7,
            'type': 'audio',
            'reason': 'Audio activity detected'
        })
        
        return highlights
    
    def _parse_ambient_audio(self, stderr_output: str) -> List[Dict[str, Any]]:
        """Parse ambient audio patterns (simplified)."""
        # Mock implementation for scenic content
        highlights = []
        
        highlights.append({
            'start': 120,
            'end': 175,
            'score': 0.6,
            'type': 'ambient',
            'reason': 'Calm ambient audio'
        })
        
        return highlights
    
    # Removed: _load_usage_tracking and any hf_usage.json handling
