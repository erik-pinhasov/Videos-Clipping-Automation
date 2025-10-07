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
        
        # Viral subtitle styling (consistent professional look)
        self.subtitle_styles = {
            'naturesmomentstv': { 'font': 'Arial', 'size': 52, 'color': 'white', 'outline_color': 'black', 'outline_width': 6, 'bold': 1, 'shadow': 0, 'spacing': 0, 'margin_v': 110, 'position': 'bottom' },
            'navwildanimaldocumentary': { 'font': 'Arial', 'size': 52, 'color': 'white', 'outline_color': 'black', 'outline_width': 6, 'bold': 1, 'shadow': 0, 'spacing': 0, 'margin_v': 110, 'position': 'bottom' },
            'wildnatureus2024': { 'font': 'Arial', 'size': 52, 'color': 'white', 'outline_color': 'black', 'outline_width': 6, 'bold': 1, 'shadow': 0, 'spacing': 0, 'margin_v': 110, 'position': 'bottom' },
            'ScenicScenes': { 'font': 'Arial', 'size': 52, 'color': 'white', 'outline_color': 'black', 'outline_width': 6, 'bold': 1, 'shadow': 0, 'spacing': 0, 'margin_v': 110, 'position': 'bottom' }
        }
        
    # OpenAI API for speech-to-text
    
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
                clip_number = i + 1
                try:
                    # OpenAI API for speech-to-text
                    self.openai_api_key = getattr(self.config, 'OPENAI_API_KEY', None)
                    # Create base clip
                    clip_path = self._create_base_clip(
                        video_path, highlight, video_id, clip_number
                    )
                    
                    if not clip_path:
                        self.logger.error(f"  Failed to create base clip {clip_number}")
                        continue
                    
                    # Add subtitles unless disabled by config
                    if getattr(self.config, 'SUBTITLES_MODE', 'exact') == 'off':
                        final_clip_path = clip_path
                    else:
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
                    self.logger.error(f"  Failed to create clip {clip_number}: {e}")
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
            
            # Clamp duration to YouTube Shorts requirements: 10s–55s
            min_len, max_len = 10, 55
            if duration > max_len:
                mid = (start_time + end_time) / 2.0
                start_time = max(0, mid - max_len/2.0)
                end_time = start_time + max_len
            elif duration < min_len:
                extend = min_len - duration
                start_time = max(0, start_time - extend/2.0)
                end_time = start_time + min_len
            
            # Output path
            clip_filename = f"{video_id}_clip_{clip_number}.mp4"
            clip_path = os.path.join(self.config.CLIPS_DIR, clip_filename)
            
            # 9:16 layout: blurred background + foreground filling frame (no tiny center box)
            vf = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                "boxblur=luma_radius=25:luma_power=1:chroma_radius=25:chroma_power=1[bg];"
                "[0:v]scale=-2:1920:flags=lanczos,crop=1080:1920[fg];"
                "[bg][fg]overlay=0:0,format=yuv420p"
            )
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_time),
                '-i', video_path,
                '-t', str(end_time - start_time),
                '-filter_complex', vf,
                '-r', '30',
                '-s', '1080x1920',
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-crf', '21',
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
        """Generate transcript using OpenAI Whisper API (exact segments when available)."""
        try:
            # Extract audio from clip
            audio_path = self._extract_audio_for_transcription(clip_path)
            if not audio_path:
                return None
            transcript = self._transcribe_with_openai(audio_path)
            # Cleanup temp audio file
            try:
                if Path(audio_path).exists():
                    Path(audio_path).unlink()
            except:
                pass
            if transcript:
                # If we got structured segments, prefer them; otherwise enhance plain text
                if isinstance(transcript, dict) and 'segments' in transcript:
                    return transcript
                enhanced_transcript = self._enhance_transcript(transcript, channel)
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
    
    def _transcribe_with_openai(self, audio_path: str) -> Optional[Dict[str, Any] | str]:
        """Transcribe audio using OpenAI Whisper API.
        Returns:
          - dict with 'segments' when verbose JSON is available (exact narrator timing)
          - or plain string text when only 'text' is returned
        """
        try:
            import requests
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            api_url = "https://api.openai.com/v1/audio/transcriptions"
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            files = {
                "file": ("audio.wav", audio_data, "audio/wav")
            }
            model = getattr(self.config, 'WHISPER_MODEL', 'whisper-1')
            # Request verbose_json for per-segment timing when available
            data = {"model": model, "response_format": "verbose_json"}
            response = requests.post(api_url, headers=headers, files=files, data=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                # Prefer segments if provided
                if isinstance(result, dict) and 'segments' in result and result.get('segments'):
                    segments = []
                    for seg in result['segments']:
                        try:
                            segments.append({
                                'text': seg.get('text', '').strip(),
                                'start': float(seg.get('start', 0.0)),
                                'end': float(seg.get('end', 0.0))
                            })
                        except Exception:
                            continue
                    return {'segments': segments, 'full_text': result.get('text', '').strip()}
                # Fall back to plain text
                return result.get('text', '').strip()
            elif response.status_code == 429:
                self.logger.warning("OpenAI API rate limit hit")
                return None
            else:
                self.logger.error(f"OpenAI transcription failed: {response.status_code} {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"OpenAI transcription error: {e}")
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
            
            # Helper to wrap and style text for viral readability
            def wrap_text(text: str, max_chars: int = 28) -> str:
                words = text.split()
                lines = []
                line = ''
                for w in words:
                    candidate = (line + ' ' + w).strip()
                    if len(candidate) <= max_chars:
                        line = candidate
                    else:
                        if line:
                            lines.append(line)
                        line = w
                if line:
                    lines.append(line)
                if len(lines) > 2:
                    lines = [lines[0], ' '.join(lines[1:])]
                return '\n'.join(lines)

            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments):
                    start_time = self._seconds_to_srt_time(segment['start'])
                    end_time = self._seconds_to_srt_time(segment['end'])
                    text = segment['text'].strip()
                    if getattr(self.config, 'SUBTITLES_MODE', 'exact') != 'off':
                        text = text.upper()
                    text = wrap_text(text)
                    
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
            self.logger.debug(f"Using subtitle filter: {subtitle_filter}")
            
            cmd = [
                'ffmpeg', '-y',
                '-i', clip_path,
                '-vf', subtitle_filter,
                '-c:v', 'libx264',
                '-preset', 'slow',
                '-crf', '21',
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
        """Build FFmpeg subtitle filter with viral styling (properly escaped)."""
        try:
            # Escape path for FFmpeg on Windows (backslashes and colons)
            escaped_srt_path = srt_path.replace('\\', '\\\\').replace(':', '\\:')

            # Build single force_style string; do NOT repeat force_style to avoid filter parsing issues
            kv = []
            if style.get('font'):
                kv.append(f"FontName={style['font']}")
            if style.get('size'):
                kv.append(f"FontSize={style['size']}")
            if style.get('color'):
                kv.append(f"PrimaryColour={self._convert_color_for_subtitles(style['color'])}")
            if style.get('outline_color') and style.get('outline_width'):
                kv.append(f"OutlineColour={self._convert_color_for_subtitles(style['outline_color'])}")
                kv.append(f"Outline={style['outline_width']}")
            if style.get('bold') is not None:
                kv.append(f"Bold={style['bold']}")
            if style.get('shadow') is not None:
                kv.append(f"Shadow={style['shadow']}")
            if style.get('spacing') is not None:
                kv.append(f"Spacing={style['spacing']}")
            if style.get('margin_v') is not None:
                kv.append(f"MarginV={style['margin_v']}")
            if style.get('position') == 'bottom':
                kv.append("Alignment=2")  # Bottom center

            if kv:
                style_str = ','.join(kv)
                # Escape commas so ffmpeg doesn't split the filter graph
                style_str_escaped = style_str.replace(',', '\\,')
                return f"subtitles='{escaped_srt_path}':force_style='{style_str_escaped}'"
            else:
                return f"subtitles='{escaped_srt_path}'"

        except Exception as e:
            self.logger.debug(f"Subtitle filter building failed: {e}")
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
    
    # Removed Hugging Face usage tracking and quota logic