"""
Creates video clips with viral-style subtitles and optimal formatting for YouTube Shorts.
"""

import os
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import config
from src.core.logger import get_logger
from src.core.exceptions import ClipCreationError


class ClipCreator:
    """Creates engaging video clips with subtitles for YouTube Shorts."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Ensure clips directory exists
        Path(self.config.CLIPS_DIR).mkdir(parents=True, exist_ok=True)
        
        # Subtitle styling configurations
        self.subtitle_styles = {
            'naturesmomentstv': {
                'font': 'Arial Bold',
                'size': 24,
                'color': 'white',
                'outline_color': 'black',
                'outline_width': 2,
                'position': 'bottom'
            },
            'navwildanimaldocumentary': {
                'font': 'Arial Bold',
                'size': 26,
                'color': '#FFD700',  # Gold
                'outline_color': 'black',
                'outline_width': 3,
                'position': 'bottom'
            },
            'wildnatureus2024': {
                'font': 'Arial Bold',
                'size': 24,
                'color': '#00FF7F',  # Spring green
                'outline_color': '#006400',  # Dark green
                'outline_width': 2,
                'position': 'bottom'
            },
            'ScenicScenes': {
                'font': 'Arial Bold',
                'size': 22,
                'color': '#E6E6FA',  # Lavender
                'outline_color': '#4B0082',  # Indigo
                'outline_width': 2,
                'position': 'bottom'
            }
        }
        
        # HF API for speech-to-text
        self.hf_token = getattr(cfg, 'HUGGING_FACE_TOKEN', None)
        self.hf_headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        
        # Track HF usage
        self.hf_usage_file = "hf_subtitle_usage.json"
        self.hf_usage = self._load_hf_usage()
    
    def create_clips(self, video_path: str, highlights: List[Dict[str, Any]], 
                    video_id: str, channel: str) -> List[str]:
        """Create clips with subtitles from video highlights."""
        try:
            if not highlights:
                self.logger.warning("No highlights provided for clip creation")
                return []
            
            self.logger.info(f"Creating {len(highlights)} clips with subtitles...")
            
            created_clips = []
            
            for i, highlight in enumerate(highlights):
                try:
                    clip_number = i + 1
                    self.logger.info(f"  Creating clip {clip_number}/{len(highlights)}...")
                    
                    # Create base clip
                    clip_path = self._create_base_clip(
                        video_path, highlight, video_id, clip_number
                    )
                    
                    if not clip_path:
                        self.logger.error(f"  Failed to create base clip {clip_number}")
                        continue
                    
                    # Add subtitles
                    final_clip_path = self._add_subtitles_to_clip(
                        clip_path, highlight, channel, clip_number
                    )
                    
                    if final_clip_path and Path(final_clip_path).exists():
                        created_clips.append(final_clip_path)
                        self.logger.info(f"  ✓ Created clip {clip_number}: {Path(final_clip_path).name}")
                    else:
                        self.logger.error(f"  Failed to add subtitles to clip {clip_number}")
                        # Keep clip without subtitles as fallback
                        if clip_path and Path(clip_path).exists():
                            created_clips.append(clip_path)
                    
                except Exception as e:
                    self.logger.error(f"  Failed to create clip {i+1}: {e}")
                    continue
            
            self.logger.info(f"Successfully created {len(created_clips)} clips")
            return created_clips
            
        except Exception as e:
            raise ClipCreationError(f"Clip creation failed: {e}")
    
    def _create_base_clip(self, video_path: str, highlight: Dict[str, Any], 
                         video_id: str, clip_number: int) -> Optional[str]:
        """Create base video clip without subtitles."""
        try:
            start_time = highlight['start']
            end_time = highlight['end']
            duration = end_time - start_time
            
            # Ensure optimal duration for Shorts (45-60 seconds)
            if duration > 60:
                end_time = start_time + 58
            elif duration < 30:
                # Extend clip if too short
                extension_needed = 35 - duration
                start_time = max(0, start_time - extension_needed/2)
                end_time = end_time + extension_needed/2
            
            # Output path
            clip_filename = f"{video_id}_clip_{clip_number}.mp4"
            clip_path = os.path.join(self.config.CLIPS_DIR, clip_filename)
            
            # Create clip with optimal settings for Shorts
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_time),
                '-i', video_path,
                '-t', str(end_time - start_time),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',  # Good quality for mobile viewing
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',  # Optimize for streaming
                '-avoid_negative_ts', 'make_zero',
                clip_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and Path(clip_path).exists():
                return clip_path
            else:
                self.logger.error(f"FFmpeg clip creation failed: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"Base clip creation failed: {e}")
            return None
    
    def _add_subtitles_to_clip(self, clip_path: str, highlight: Dict[str, Any], 
                              channel: str, clip_number: int) -> Optional[str]:
        """Add engaging subtitles to video clip."""
        try:
            # Generate transcript for this clip
            transcript = self._generate_clip_transcript(clip_path, channel)
            
            if not transcript:
                self.logger.warning(f"No transcript generated for clip {clip_number}, skipping subtitles")
                return clip_path
            
            # Create subtitle file
            srt_path = self._create_subtitle_file(transcript, clip_path, channel)
            
            if not srt_path:
                self.logger.warning(f"Subtitle file creation failed for clip {clip_number}")
                return clip_path
            
            # Apply subtitles to video
            final_path = self._burn_subtitles_to_video(clip_path, srt_path, channel)
            
            # Cleanup temporary files
            try:
                if Path(srt_path).exists():
                    Path(srt_path).unlink()
            except:
                pass
            
            return final_path if final_path else clip_path
            
        except Exception as e:
            self.logger.error(f"Subtitle addition failed: {e}")
            return clip_path
    
    def _generate_clip_transcript(self, clip_path: str, channel: str) -> Optional[Dict[str, Any]]:
        """Generate transcript using HF Whisper model."""
        try:
            # Check HF quota
            if self._check_hf_quota_exceeded():
                self.logger.warning("HF quota exceeded, skipping subtitle generation")
                return None
            
            # Extract audio from clip
            audio_path = self._extract_audio_for_transcription(clip_path)
            
            if not audio_path:
                return None
            
            # Get transcript from HF
            transcript = self._transcribe_with_hf(audio_path)
            
            # Cleanup temp audio file
            try:
                if Path(audio_path).exists():
                    Path(audio_path).unlink()
            except:
                pass
            
            if transcript:
                # Enhance transcript with AI if available
                enhanced_transcript = self._enhance_transcript(transcript, channel)
                self._track_hf_usage()
                return enhanced_transcript
            
            return None
            
        except Exception as e:
            self.logger.error(f"Transcript generation failed: {e}")
            return None
    
    def _extract_audio_for_transcription(self, clip_path: str) -> Optional[str]:
        """Extract audio from clip for transcription."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_audio:
                audio_path = tmp_audio.name
            
            # Extract audio using ffmpeg
            cmd = [
                'ffmpeg', '-y',
                '-i', clip_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # WAV format
                '-ar', '16000',  # 16kHz for Whisper
                '-ac', '1',  # Mono
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and Path(audio_path).exists():
                return audio_path
            else:
                self.logger.error(f"Audio extraction failed: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"Audio extraction error: {e}")
            return None
    
    def _transcribe_with_hf(self, audio_path: str) -> Optional[str]:
        """Transcribe audio using HF Whisper model."""
        try:
            # Read audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            # HF Whisper API endpoint
            api_url = "https://api-inference.huggingface.co/models/openai/whisper-base"
            
            response = requests.post(
                api_url,
                headers=self.hf_headers,
                data=audio_data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('text', '').strip()
            elif response.status_code == 429:
                self.logger.warning("HF API rate limit hit")
                return None
            else:
                self.logger.error(f"HF transcription failed: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"HF transcription error: {e}")
            return None
    
    def _enhance_transcript(self, raw_transcript: str, channel: str) -> Dict[str, Any]:
        """Enhance transcript for engaging subtitles."""
        try:
            # Try to enhance with OpenAI if available
            from src.services.metadata_service import MetadataService
            
            metadata_service = MetadataService(self.config)
            enhanced_text = metadata_service.enhance_subtitles(raw_transcript, channel)
            
            # Break into timed segments (simplified)
            words = enhanced_text.split()
            segments = []
            
            # Create segments of ~5-7 words each for good readability
            segment_size = 6
            duration_per_segment = 2.5  # 2.5 seconds per segment
            
            for i in range(0, len(words), segment_size):
                segment_words = words[i:i + segment_size]
                start_time = i / segment_size * duration_per_segment
                end_time = start_time + duration_per_segment
                
                segments.append({
                    'text': ' '.join(segment_words),
                    'start': start_time,
                    'end': end_time
                })
            
            return {
                'segments': segments,
                'full_text': enhanced_text
            }
            
        except Exception as e:
            self.logger.debug(f"Transcript enhancement failed: {e}")
            # Return basic segmentation
            words = raw_transcript.split()
            segments = []
            
            for i in range(0, len(words), 5):
                segment_words = words[i:i + 5]
                start_time = i / 5 * 2.0
                end_time = start_time + 2.0
                
                segments.append({
                    'text': ' '.join(segment_words),
                    'start': start_time,
                    'end': end_time
                })
            
            return {
                'segments': segments,
                'full_text': raw_transcript
            }
    
    def _create_subtitle_file(self, transcript: Dict[str, Any], clip_path: str, channel: str) -> Optional[str]:
        """Create SRT subtitle file."""
        try:
            clip_name = Path(clip_path).stem
            srt_path = os.path.join(self.config.CLIPS_DIR, f"{clip_name}_subtitles.srt")
            
            segments = transcript.get('segments', [])
            
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments):
                    start_time = self._seconds_to_srt_time(segment['start'])
                    end_time = self._seconds_to_srt_time(segment['end'])
                    text = segment['text'].strip()
                    
                    if text:  # Only write non-empty segments
                        f.write(f"{i + 1}\n")
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{text}\n\n")
            
            return srt_path if Path(srt_path).exists() else None
            
        except Exception as e:
            self.logger.error(f"Subtitle file creation failed: {e}")
            return None
    
    def _burn_subtitles_to_video(self, clip_path: str, srt_path: str, channel: str) -> Optional[str]:
        """Burn subtitles into video with viral styling."""
        try:
            style = self.subtitle_styles.get(channel, self.subtitle_styles['naturesmomentstv'])
            
            # Output path
            clip_name = Path(clip_path).stem
            output_path = os.path.join(self.config.CLIPS_DIR, f"{clip_name}_final.mp4")
            
            # Build subtitle filter with viral styling
            subtitle_filter = self._build_subtitle_filter(srt_path, style)
            
            cmd = [
                'ffmpeg', '-y',
                '-i', clip_path,
                '-vf', subtitle_filter,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'copy',  # Copy audio without re-encoding
                '-movflags', '+faststart',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and Path(output_path).exists():
                # Remove original clip to save space
                try:
                    Path(clip_path).unlink()
                except:
                    pass
                
                return output_path
            else:
                self.logger.error(f"Subtitle burning failed: {result.stderr}")
                return clip_path  # Return original as fallback
                
        except Exception as e:
            self.logger.error(f"Subtitle burning error: {e}")
            return clip_path
    
    def _build_subtitle_filter(self, srt_path: str, style: Dict[str, str]) -> str:
        """Build FFmpeg subtitle filter with viral styling."""
        try:
            # Escape path for FFmpeg
            escaped_srt_path = srt_path.replace('\\', '\\\\').replace(':', '\\:')
            
            # Base subtitle filter
            subtitle_filter = f"subtitles='{escaped_srt_path}'"
            
            # Add styling
            style_options = []
            
            # Font and size
            if style.get('font'):
                style_options.append(f"force_style='FontName={style['font']}'")
            
            if style.get('size'):
                style_options.append(f"force_style='FontSize={style['size']}'")
            
            # Colors
            if style.get('color'):
                # Convert color name/hex to subtitle format
                color = self._convert_color_for_subtitles(style['color'])
                style_options.append(f"force_style='PrimaryColour={color}'")
            
            if style.get('outline_color') and style.get('outline_width'):
                outline_color = self._convert_color_for_subtitles(style['outline_color'])
                outline_width = style['outline_width']
                style_options.append(f"force_style='OutlineColour={outline_color},Outline={outline_width}'")
            
            # Positioning
            if style.get('position') == 'bottom':
                style_options.append("force_style='Alignment=2'")  # Bottom center
            
            # Combine all style options
            if style_options:
                full_style = ','.join(style_options)
                subtitle_filter = f"subtitles='{escaped_srt_path}':{full_style}"
            
            return subtitle_filter
            
        except Exception as e:
            self.logger.debug(f"Subtitle filter building failed: {e}")
            # Return basic filter as fallback
            escaped_srt_path = srt_path.replace('\\', '\\\\').replace(':', '\\:')
            return f"subtitles='{escaped_srt_path}'"
    
    def _convert_color_for_subtitles(self, color: str) -> str:
        """Convert color to subtitle format."""
        try:
            color_map = {
                'white': '&H00FFFFFF',
                'black': '&H00000000', 
                'red': '&H000000FF',
                'green': '&H0000FF00',
                'blue': '&H00FF0000',
                '#FFD700': '&H0000D7FF',  # Gold
                '#00FF7F': '&H007FFF00',  # Spring green
                '#006400': '&H00006400',  # Dark green
                '#E6E6FA': '&H00FAE6E6',  # Lavender
                '#4B0082': '&H0082004B'   # Indigo
            }
            
            return color_map.get(color, '&H00FFFFFF')  # Default to white
            
        except:
            return '&H00FFFFFF'
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format."""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            milliseconds = int((seconds % 1) * 1000)
            
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
            
        except:
            return "00:00:00,000"
    
    def _load_hf_usage(self) -> Dict[str, Any]:
        """Load HF usage tracking for subtitles."""
        try:
            if Path(self.hf_usage_file).exists():
                with open(self.hf_usage_file, 'r') as f:
                    data = json.load(f)
                
                from datetime import datetime
                today = datetime.now().strftime('%Y-%m-%d')
                if data.get('date') == today:
                    return data
            
            from datetime import datetime
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'calls': 0
            }
            
        except:
            from datetime import datetime
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'calls': 0
            }
    
    def _check_hf_quota_exceeded(self) -> bool:
        """Check if HF quota is exceeded for subtitle generation."""
        daily_limit = 30  # Conservative limit for transcription
        return self.hf_usage['calls'] >= daily_limit
    
    def _track_hf_usage(self) -> None:
        """Track HF usage for subtitles."""
        try:
            self.hf_usage['calls'] += 1
            
            with open(self.hf_usage_file, 'w') as f:
                json.dump(self.hf_usage, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Could not track HF usage: {e}")