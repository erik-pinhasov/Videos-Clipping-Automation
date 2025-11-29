import os
import tempfile
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import openai
import config
from src.core.logger import get_logger

_VOSK_AVAILABLE = False
def _vosk_available() -> bool:
    global _VOSK_AVAILABLE
    if _VOSK_AVAILABLE:
        return True
    try:
        import importlib
        importlib.import_module('vosk')
        _VOSK_AVAILABLE = True
        return True
    except Exception:
        return False


class HighlightDetector:
    """Detects video highlights using AI and local analysis methods."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Default detection strategy for nature/wildlife content
        self.default_strategy = 'nature_documentary'
            
    def detect(self, video_path: str, channel: str) -> List[Dict[str, Any]]:
        """Detect highlights using intelligent analysis."""
        try:
            strategy = self.default_strategy
            self.logger.info(f"Using '{strategy}' detection strategy for highlight extraction")
            
            # Get video info first
            video_duration = self._get_video_duration(video_path)
            if video_duration < 60:  # Too short
                return []
            
            # Use multiple detection methods (AI captions first for quality, then local fallbacks)
            highlights = []

            # AI path: get compact transcript and ask AI to select windows
            try:
                ai_highlights = self._detect_with_ai_transcript(video_path, channel, video_duration)
                if ai_highlights:
                    highlights.extend(ai_highlights)
            except Exception as e:
                self.logger.debug(f"AI transcript-based detection failed: {e}")
            
            # Method 1: Local audio analysis (free, unlimited)
            audio_highlights = self._detect_audio_peaks(video_path, strategy)
            highlights.extend(audio_highlights)
            
            # Method 2: Local motion analysis (free, unlimited)  
            motion_highlights = self._detect_motion_peaks(video_path, strategy)
            highlights.extend(motion_highlights)
                        
            # Process and rank highlights
            final_highlights = self._process_highlights(highlights, video_duration, strategy)
            
            self.logger.info(f"Detected {len(final_highlights)} highlight segments using {strategy} strategy")
            
            return final_highlights
            
        except Exception as e:
            self.logger.error(f"Highlight detection failed: {e}")
            # Return basic highlights as fallback
            return self._create_fallback_highlights(video_path)

    def _detect_with_ai_transcript(self, video_path: str, channel: str, video_duration: float) -> List[Dict[str, Any]]:
        """Token-efficient AI highlight selection using condensed transcript and niche-aware scoring.

        Steps:
        1) Extract a sparse transcript: prefer built-in captions via ffmpeg/yt-dlp if available; else sample ASR locally from 1–2% of frames/audio windows (cost-free), then condense with LLM.
        2) Ask LLM to propose top highlight windows (10–55s), returning timestamps.
        """
        try:
            # Step 1: Try embedded subtitles first (most token-efficient)
            sparse_transcript = self._extract_embedded_captions(video_path)
            if not sparse_transcript:
                # Fallback: generate a very lightweight local "gist" transcript by sampling audio
                sparse_transcript = self._sample_local_gist_transcript(video_path)

            if not sparse_transcript:
                return []

            # Step 2: Condense transcript and request windows from OpenAI
            strategy = self.default_strategy

            prompt = f"""
You are selecting the most engaging short highlight windows from a long {strategy} video (nature/wildlife).
Given this sparse transcript (key lines only), output 8–20 candidate highlight segments.

Rules:
- Each segment must be between 10 and 55 seconds long.
- Prefer emotionally engaging wildlife moments (hunts, interactions, reveals, funny/rare behavior) or epic scenic beats (panoramas, transitions).
- Spread picks across the full timeline; avoid overlapping segments.
- Return structured JSON only, as an array of objects: [{{"start": seconds, "end": seconds, "reason": "short reason"}}, ...]

Sparse transcript (approximate timeline):
{sparse_transcript}
"""

            # Initialize OpenAI client
            client = openai.OpenAI(api_key=self.config.OPENAI_API_KEY)
            
            resp = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You choose time windows for viral short clips from nature/wildlife content strictly within given constraints."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=700,
                temperature=0.4,
            )

            content = resp.choices[0].message.content.strip()
            import json as _json
            windows = []
            try:
                windows = _json.loads(content)
            except Exception:
                # Try to extract JSON from text
                if '[' in content:
                    content = content[content.index('['):]
                    r = content.rfind(']')
                    if r != -1:
                        windows = _json.loads(content[:r+1])

            results: List[Dict[str, Any]] = []
            for w in windows:
                try:
                    s = max(0.0, float(w.get('start', 0.0)))
                    e = min(video_duration - 1.0, float(w.get('end', 0.0)))
                    if e > s and (e - s) >= 10 and (e - s) <= 55:
                        results.append({
                            'start': s,
                            'end': e,
                            'score': 0.9,
                            'type': 'ai',
                            'reason': w.get('reason', 'AI-selected highlight')[:80]
                        })
                except Exception:
                    continue

            return results[:40]
        except Exception as e:
            self.logger.debug(f"AI transcript selection error: {e}")
            return []

    def _extract_embedded_captions(self, video_path: str) -> str:
        """Try to extract embedded subtitles/captions with ffmpeg (no tokens)."""
        try:
            # Dump first subtitle stream to srt if present
            tmp_srt = Path(video_path).with_suffix('.captions.srt')
            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-map', '0:s:0', tmp_srt.as_posix()
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and tmp_srt.exists():
                text = tmp_srt.read_text(encoding='utf-8', errors='ignore')
                tmp_srt.unlink(missing_ok=True)
                # Compress to a compact timeline string
                return self._compact_srt(text)
            return ""
        except Exception:
            return ""

    def _sample_local_gist_transcript(self, video_path: str) -> str:
        """Generate a very short gist of the audio by sampling sparse segments and running local ASR (no OpenAI)."""
        try:
            # Sample 6 short 8s windows spread across the video
            dur = self._get_video_duration(video_path)
            if dur <= 0:
                return ""
            stamps = [max(0, (i/6.0)*dur) for i in range(1,6)]
            lines = []
            for ts in stamps:
                try:
                    # Extract small audio chunk
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpa:
                        ap = tmpa.name
                    cmd = ['ffmpeg', '-y', '-ss', str(ts), '-t', '8', '-i', video_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', ap]
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
                    if r.returncode != 0:
                        continue
                    # Use VOSK (if available) or leave markers only
                    try:
                        if not _vosk_available():
                            raise RuntimeError("vosk not available")
                        import wave, importlib
                        wf = wave.open(ap, 'rb')
                        vosk = importlib.import_module('vosk')  # type: ignore
                        model = vosk.Model(lang='en-us')
                        rec = vosk.KaldiRecognizer(model, wf.getframerate())
                        text_accum = []
                        while True:
                            data = wf.readframes(4000)
                            if len(data) == 0:
                                break
                            if rec.AcceptWaveform(data):
                                text_accum.append(rec.Result())
                        text_accum.append(rec.FinalResult())
                        import json as _j
                        words = ' '.join([_j.loads(x).get('text', '') for x in text_accum])
                        if words.strip():
                            lines.append(f"{int(ts)}s: {words.strip()}")
                    except Exception:
                        # If no vosk, record a timestamp marker instead to still guide spacing
                        lines.append(f"{int(ts)}s: [audio sample]")
                finally:
                    try:
                        os.unlink(ap)
                    except Exception:
                        pass
            return '\n'.join(lines)
        except Exception:
            return ""

    def _compact_srt(self, srt_text: str) -> str:
        """Reduce SRT to a compact timeline text to keep tokens low."""
        try:
            out = []
            for block in srt_text.split('\n\n'):
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                if len(lines) >= 3:
                    time_line = lines[1]
                    text_line = ' '.join(lines[2:])
                    out.append(f"{time_line} | {text_line}")
            # Keep only first ~120 lines to cap tokens
            return '\n'.join(out[:120])
        except Exception:
            return ""
    
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
                        # Use tighter windows around scene changes for short-form
                        pre = 12.0
                        post = 16.0
                        highlights.append({
                            'start': max(0, timestamp - pre),
                            'end': timestamp + post,
                            'score': 0.75,
                            'type': 'motion',
                            'reason': 'Scene change detected'
                        })
                    except (ValueError, IndexError):
                        continue
            
            return highlights[:60]  # Allow more motion peaks for long videos
            
        except Exception as e:
            self.logger.debug(f"Motion peak detection failed: {e}")
            return []
    
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
                # Prefer shorter fallback windows to keep clips punchy
                fallback = self._generate_evenly_spaced_highlights(video_duration, length=28, stride=110)

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

    def _generate_evenly_spaced_highlights(self, duration: float, length: int = 28, stride: int = 110) -> List[Dict[str, Any]]:
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
                'score': 0.45,
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
                'end': min(duration - 5, 28),
                'score': 0.5,
                'type': 'fallback',
                'reason': 'Default highlight for short video'
            })
        elif duration < 600:  # Less than 10 minutes
            # Create 2 highlights
            highlights.extend([
                {
                    'start': 30,
                    'end': 30 + 28,
                    'score': 0.6,
                    'type': 'fallback',
                    'reason': 'Early highlight'
                },
                {
                    'start': duration / 2,
                    'end': duration / 2 + 30,
                    'score': 0.6,
                    'type': 'fallback',
                    'reason': 'Mid-video highlight'
                }
            ])
        else:  # 10+ minutes
            # Create many evenly spaced highlights (~every 2 minutes)
            highlights = self._generate_evenly_spaced_highlights(duration, length=28, stride=110)
        
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