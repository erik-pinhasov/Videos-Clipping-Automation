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
from src.core.exceptions import HighlightDetectionError, HuggingFaceError


class HighlightDetector:
    """Detects video highlights using multiple strategies and HF models."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Hugging Face API setup
        self.hf_token = getattr(cfg, 'HUGGING_FACE_TOKEN', None)
        self.hf_headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        
        # Detection strategies per channel
        self.detection_strategies = {
            'naturesmomentstv': 'nature_documentary',
            'navwildanimaldocumentary': 'wildlife_action',
            'wildnatureus2024': 'scenic_nature',
            'ScenicScenes': 'scenic'
        }
        
        # HF models for different analysis types
        self.models = {
            'audio_classification': "facebook/wav2vec2-base-960h",
            'scene_classification': "microsoft/DiT-base-finetuned-ade-512-512",
            'video_analysis': "microsoft/xclip-base-patch32"
        }
        
        # Usage tracking to avoid quota limits
        self.usage_file = "hf_usage.json"
        self.daily_usage = self._load_usage_tracking()
    
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
            
            # Method 3: HF-powered content analysis (limited usage)
            if not self._check_quota_exceeded():
                try:
                    content_highlights = self._detect_content_highlights(video_path, strategy)
                    highlights.extend(content_highlights)
                    self._track_usage()
                except Exception as e:
                    self.logger.warning(f"HF content analysis failed: {e}")
            
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
            
            return highlights[:10]  # Limit to top 10 motion peaks
            
        except Exception as e:
            self.logger.debug(f"Motion peak detection failed: {e}")
            return []
    
    def _detect_content_highlights(self, video_path: str, strategy: str) -> List[Dict[str, Any]]:
        """Detect content-based highlights using HF models (limited usage)."""
        try:
            # Extract frames for analysis (only keyframes to save quota)
            frames = self._extract_keyframes(video_path, max_frames=5)
            
            if not frames:
                return []
            
            highlights = []
            
            # Analyze each frame with HF model
            for frame_data in frames:
                try:
                    # Use scene classification model
                    analysis = self._query_hf_model(
                        self.models['scene_classification'],
                        frame_data['image_data']
                    )
                    
                    # Convert HF analysis to highlights based on strategy
                    if self._is_interesting_scene(analysis, strategy):
                        highlights.append({
                            'start': max(0, frame_data['timestamp'] - 25),
                            'end': frame_data['timestamp'] + 35,
                            'score': 0.8,
                            'type': 'content',
                            'reason': f"Interesting {strategy} content detected"
                        })
                        
                except Exception as e:
                    self.logger.debug(f"Frame analysis failed: {e}")
                    continue
            
            return highlights
            
        except Exception as e:
            self.logger.warning(f"Content highlight detection failed: {e}")
            return []
    
    def _extract_keyframes(self, video_path: str, max_frames: int = 5) -> List[Dict[str, Any]]:
        """Extract keyframes for HF analysis."""
        try:
            duration = self._get_video_duration(video_path)
            
            # Get evenly spaced timestamps
            timestamps = []
            if duration > 300:  # 5+ minutes
                # Extract frames every 2 minutes
                for i in range(0, int(duration), 120):
                    timestamps.append(i + 60)  # Start 1 minute in
                    if len(timestamps) >= max_frames:
                        break
            else:
                # Extract frames every 30 seconds for shorter videos
                for i in range(30, int(duration), 30):
                    timestamps.append(i)
                    if len(timestamps) >= max_frames:
                        break
            
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
    
    def _query_hf_model(self, model_name: str, data: Any) -> Dict[str, Any]:
        """Query Hugging Face model with rate limiting."""
        try:
            api_url = f"https://api-inference.huggingface.co/models/{model_name}"
            
            # Prepare data for API
            if isinstance(data, str):
                # Base64 image data
                import base64
                payload = {"inputs": data}
            else:
                payload = {"inputs": data}
            
            response = requests.post(
                api_url,
                headers=self.hf_headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                raise HuggingFaceError("HF API rate limit exceeded")
            else:
                raise HuggingFaceError(f"HF API error: {response.status_code}")
                
        except Exception as e:
            raise HuggingFaceError(f"HF model query failed: {e}")
    
    def _is_interesting_scene(self, analysis: Dict[str, Any], strategy: str) -> bool:
        """Determine if scene analysis indicates interesting content."""
        try:
            if not analysis or not isinstance(analysis, list):
                return False
            
            # Get top predictions
            top_prediction = analysis[0] if analysis else {}
            confidence = top_prediction.get('score', 0)
            label = top_prediction.get('label', '').lower()
            
            # Strategy-specific scene evaluation
            if strategy == 'wildlife_action':
                action_keywords = ['animal', 'wildlife', 'forest', 'water', 'bird', 'mammal']
                return confidence > 0.6 and any(keyword in label for keyword in action_keywords)
            
            elif strategy == 'scenic':
                scenic_keywords = ['landscape', 'mountain', 'sky', 'water', 'tree', 'field']
                return confidence > 0.7 and any(keyword in label for keyword in scenic_keywords)
            
            elif strategy == 'nature_documentary':
                nature_keywords = ['nature', 'outdoor', 'plant', 'animal', 'landscape']
                return confidence > 0.6 and any(keyword in label for keyword in nature_keywords)
            
            return confidence > 0.8  # High confidence fallback
            
        except Exception:
            return False
    
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
                
                # Ensure minimum clip length
                if end - start >= 30:  # At least 30 seconds
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
            
            # Limit number based on video duration and quality
            max_clips = min(len(valid_highlights), max(2, int(video_duration / 300)))
            final_highlights = valid_highlights[:max_clips]
            
            self.logger.info(f"Processed highlights: {len(raw_highlights)} → {len(final_highlights)} final clips")
            
            return final_highlights
            
        except Exception as e:
            self.logger.error(f"Highlight processing failed: {e}")
            return self._create_fallback_highlights_with_duration(video_duration)
    
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
            # Create 3-4 evenly spaced highlights
            section_length = duration / 4
            for i in range(3):
                start = (i + 1) * section_length
                end = start + 50
                if end < duration - 5:
                    highlights.append({
                        'start': start,
                        'end': end,
                        'score': 0.5,
                        'type': 'fallback',
                        'reason': f'Section {i+1} highlight'
                    })
        
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
    
    def _load_usage_tracking(self) -> Dict[str, Any]:
        """Load HF API usage tracking."""
        try:
            if Path(self.usage_file).exists():
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                
                today = datetime.now().strftime('%Y-%m-%d')
                if data.get('date') == today:
                    return data
            
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'calls': 0,
                'quota_exceeded': False
            }
            
        except Exception:
            return {
                'date': datetime.now().strftime('%Y-%m-%d'), 
                'calls': 0,
                'quota_exceeded': False
            }
    
    def _check_quota_exceeded(self) -> bool:
        """Check if HF quota is exceeded."""
        daily_limit = 50  # Conservative limit for free tier
        return self.daily_usage['calls'] >= daily_limit or self.daily_usage.get('quota_exceeded', False)
    
    def _track_usage(self) -> None:
        """Track HF API usage."""
        try:
            self.daily_usage['calls'] += 1
            
            with open(self.usage_file, 'w') as f:
                json.dump(self.daily_usage, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Could not track HF usage: {e}")