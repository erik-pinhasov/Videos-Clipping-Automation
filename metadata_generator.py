#!/usr/bin/env python3
import os
import json
import sys
import logging
from pathlib import Path
from typing import Dict, Any
import subprocess
import argparse

import openai
from openai import OpenAI
from dotenv import load_dotenv

import config

# 1) Load your .env automatically
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Initialize global variables
OPENAI_KEY = None
client = None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# 5) Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("metadata")

def initialize_openai(api_key=None):
    """Initialize OpenAI client with the provided or default API key."""
    global OPENAI_KEY, client
    OPENAI_KEY = api_key or os.getenv("OPENAI_API_KEY")
    if not OPENAI_KEY:
        raise ValueError("Missing OpenAI API key")
    
    openai.api_key = OPENAI_KEY
    client = OpenAI(api_key=OPENAI_KEY)

# Initialize OpenAI with default settings
try:
    initialize_openai()
except ValueError:
    # Will be initialized later when needed
    pass

def chunk_video_audio(video_path: str, chunk_duration: int = 300) -> list:
    """Split video audio into chunks for processing."""
    chunks = []
    
    # Get video duration first
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_entries', 'format=duration',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        total_duration = float(info['format']['duration'])
    except Exception as e:
        logging.error("Failed to get video duration: %s", e)
        return chunks

    # Create chunks
    chunk_count = int(total_duration // chunk_duration) + 1
    
    for i in range(chunk_count):
        start_time = i * chunk_duration
        end_time = min((i + 1) * chunk_duration, total_duration)
        
        if start_time >= total_duration:
            break
            
        # Extract audio chunk
        chunk_path = os.path.join(config.AUDIO_DIR, f"chunk_{i}_{os.path.basename(video_path)}.wav")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-ss', str(start_time),
            '-t', str(end_time - start_time),
            '-vn',  # No video
            '-acodec', 'pcm_s16le',
            '-ar', '16000',  # 16kHz for better transcription
            chunk_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            chunks.append({
                'path': chunk_path,
                'start': start_time,
                'end': end_time
            })
        except subprocess.CalledProcessError as e:
            logging.error("Failed to extract chunk %d: %s", i, e)
            
    return chunks

def transcribe_audio_chunks(chunks: list) -> str:
    """Transcribe audio chunks using OpenAI Whisper."""
    if not client:
        raise ValueError("OpenAI client not initialized")
    
    full_transcript = []
    
    for chunk in chunks:
        try:
            with open(chunk['path'], 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                full_transcript.append(transcript.text)
                logging.info("Transcribed chunk: %.1fs-%.1fs", chunk['start'], chunk['end'])
        except Exception as e:
            logging.error("Failed to transcribe chunk %s: %s", chunk['path'], e)
            full_transcript.append("[Transcription failed]")
    
    # Cleanup chunk files
    for chunk in chunks:
        try:
            os.unlink(chunk['path'])
        except Exception:
            pass
    
    return " ".join(full_transcript)

def generate_metadata_from_transcript(transcript: str, video_duration: float) -> Dict[str, Any]:
    """Generate video metadata using OpenAI based on transcript."""
    if not client:
        raise ValueError("OpenAI client not initialized")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a YouTube content specialist. Generate engaging metadata for wildlife/nature videos.
                    Return JSON with: title, description, tags (array), category_id (number).
                    Keep titles under 100 characters, descriptions engaging but concise.
                    Use category_id 15 for Pets & Animals, 17 for Sports, 19 for Travel & Events."""
                },
                {
                    "role": "user",
                    "content": f"Create metadata for this {video_duration:.0f}-second nature video transcript: {transcript[:2000]}..."
                }
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        metadata = json.loads(response.choices[0].message.content)
        
        # Add default values if missing
        metadata.setdefault("category_id", 15)  # Pets & Animals
        metadata.setdefault("privacy_status", "public")
        metadata.setdefault("tags", ["nature", "wildlife", "animals"])
        
        return metadata
        
    except Exception as e:
        logging.error("Failed to generate metadata from transcript: %s", e)
        return {
            "title": "Amazing Wildlife Video",
            "description": "Discover the wonders of nature in this captivating wildlife video.",
            "tags": ["nature", "wildlife", "animals", "documentary"],
            "category_id": 15,
            "privacy_status": "public"
        }

def generate_metadata(video_path: str, chunk_secs: int = 300) -> Dict[str, Any]:
    """
    Generate metadata for a video by transcribing and analyzing its audio content.
    
    Args:
        video_path: Path to the video file
        chunk_secs: Duration of audio chunks for processing (default 300 seconds)
    """
    logging.info("Generating metadata for: %s", video_path)
    
    # Ensure OpenAI client is initialized
    if not client:
        try:
            initialize_openai()
        except ValueError as e:
            logging.error("Failed to initialize OpenAI: %s", e)
            return {
                "title": f"Wildlife Video - {Path(video_path).stem}",
                "description": "An amazing wildlife and nature video showcasing the beauty of our natural world.",
                "tags": ["nature", "wildlife", "animals", "documentary"],
                "category_id": 15,
                "privacy_status": "public"
            }
    
    try:
        # 1) Extract and chunk audio
        chunks = chunk_video_audio(video_path, chunk_secs)
        if not chunks:
            raise Exception("No audio chunks extracted")
        
        # 2) Transcribe chunks
        transcript = transcribe_audio_chunks(chunks)
        if not transcript or transcript.strip() == "":
            raise Exception("Empty transcript generated")
        
        # 3) Get video duration
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_entries', 'format=duration',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        duration = float(info['format']['duration'])
        
        # 4) Generate metadata
        metadata = generate_metadata_from_transcript(transcript, duration)
        
        logging.info("Generated metadata: %s", metadata.get("title", "No title"))
        return metadata
        
    except Exception as e:
        logging.error("Failed to generate metadata: %s", e)
        # Return fallback metadata
        return {
            "title": f"Wildlife Video - {Path(video_path).stem}",
            "description": "An amazing wildlife and nature video showcasing the beauty of our natural world.",
            "tags": ["nature", "wildlife", "animals", "documentary"],
            "category_id": 15,
            "privacy_status": "public"
        }

def generate_tts_audio(metadata: Dict[str, Any], output_path: str) -> None:
    """Generate text-to-speech audio from video metadata."""
    # Ensure OpenAI client is initialized
    if not client:
        try:
            initialize_openai()
        except ValueError as e:
            logging.error("Failed to initialize OpenAI for TTS: %s", e)
            # Create silent audio as fallback
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', 'anullsrc=r=44100:cl=stereo:d=30',
                '-c:a', 'pcm_s16le',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return
    
    try:
        # Create narration script from metadata
        title = metadata.get("title", "")
        description = metadata.get("description", "")
        
        script = f"{title}. {description}"
        
        # Use OpenAI TTS
        response = client.audio.speech.create(
            model=config.TTS_MODEL,
            voice=config.TTS_VOICE,
            input=script[:4000],  # Limit length
        )
        
        # Save audio
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        logging.info("Generated TTS audio: %s", output_path)
        
    except Exception as e:
        logging.error("Failed to generate TTS audio: %s", e)
        # Create silent audio as fallback
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=stereo:d=30',
            '-c:a', 'pcm_s16le',
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)

if __name__ == "__main__":
    # 2) CLI arguments - only when run as main script
    parser = argparse.ArgumentParser(description="Generate metadata from a clip")
    parser.add_argument(
        "--openai-key",
        help="OpenAI API key; if omitted will use OPENAI_API_KEY from .env"
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=300,
        help="Seconds per Whisper chunk (default: 300s)"
    )
    parser.add_argument(
        "clip_path",
        help="Path to the video/audio file to process"
    )
    args = parser.parse_args()

    # 3) Final API key resolution
    api_key = args.openai_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        parser.error(
            "Missing OpenAI key—set OPENAI_API_KEY in .env or pass --openai-key"
        )

    # Initialize with the specified API key
    initialize_openai(api_key)

    try:
        meta = generate_metadata(args.clip_path, args.chunk_seconds)
        print(json.dumps(meta, indent=2, ensure_ascii=False))
    except Exception:
        logger.exception("generate_metadata failed")
        sys.exit(1)