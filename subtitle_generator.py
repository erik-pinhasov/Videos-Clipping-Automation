import os
import subprocess
import logging
from typing import List, Dict
from openai import OpenAI
from config import OPENAI_API_KEY, AUDIO_DIR

logger = logging.getLogger(__name__)

os.makedirs(AUDIO_DIR, exist_ok=True)

# Initialize OpenAI v1 client
client = OpenAI(api_key=OPENAI_API_KEY)

# Maximum chunk duration to avoid API size limits (in seconds)
MAX_SEGMENT_TIME = 600  # default 10 minutes


def transcribe_audio(video_path: str) -> List[Dict]:
    """
    Extract audio, split into manageable chunks if needed,
    transcribe each chunk with OpenAI Whisper, and combine segments.
    """
    base = os.path.splitext(os.path.basename(video_path))[0]
    wav_path = os.path.join(AUDIO_DIR, f"{base}.wav")

    logger.info("Extracting audio to %s", wav_path)
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000", "-ac", "1", wav_path
    ], check=True)

    # Determine total duration via ffprobe
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", wav_path
    ], capture_output=True, text=True, check=True)
    total_duration = float(result.stdout.strip())
    logger.info("Total audio duration: %.2f seconds", total_duration)

    # Split into chunks if beyond MAX_SEGMENT_TIME
    if total_duration <= MAX_SEGMENT_TIME:
        chunk_paths = [wav_path]
        offsets = [0.0]
    else:
        pattern = os.path.join(AUDIO_DIR, f"{base}_%03d.wav")
        logger.info("Splitting audio into %d-second chunks", MAX_SEGMENT_TIME)
        subprocess.run([
            "ffmpeg", "-y", "-i", wav_path,
            "-f", "segment", "-segment_time", str(MAX_SEGMENT_TIME),
            "-c", "copy", pattern
        ], check=True)
        files = sorted(
            f for f in os.listdir(AUDIO_DIR)
            if f.startswith(f"{base}_") and f.endswith(".wav")
        )
        chunk_paths = [os.path.join(AUDIO_DIR, f) for f in files]
        offsets = [i * MAX_SEGMENT_TIME for i in range(len(chunk_paths))]

    # Transcribe each chunk and adjust timestamps
    all_segments: List[Dict] = []
    for chunk_path, offset in zip(chunk_paths, offsets):
        logger.info("Transcribing chunk %s with offset %.2f", chunk_path, offset)
        with open(chunk_path, "rb") as af:
            result = client.audio.transcriptions.create(
                file=af,
                model="whisper-1",
                response_format="verbose_json"
            )
        segments = result.segments
        logger.info("Received %d segments for this chunk", len(segments))
        for seg in segments:
            all_segments.append({
                "start": seg.start + offset,
                "end": seg.end + offset,
                "text": seg.text.strip()
            })

    logger.info("Combined total transcript segments: %d", len(all_segments))
    return all_segments