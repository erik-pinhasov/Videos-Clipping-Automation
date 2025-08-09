#!/usr/bin/env python3
"""
Improved highlight detection for YouTube Shorts automation.
Uses Whisper for transcription and OpenAI embeddings for intelligent highlight scoring.
"""
import os
import argparse
import logging
from typing import List, Tuple, Dict
import numpy as np
import whisper
import openai
from openai import OpenAI

from clipper import make_clips

# === CONFIG ===
TARGET_CLIP_SECONDS = 40.0  # target length for YouTube Shorts
MIN_CLIP_SECONDS = 30.0     # shortest allowed highlight
MAX_CLIP_SECONDS = 60.0     # longest allowed highlight
WINDOW_SIZE      = 20.0     # base window length for scoring (increased for better context)
WINDOW_STEP      = 10.0     # how far the window slides (increased for less overlap)
EMBED_MODEL      = "text-embedding-ada-002"
HIGHLIGHT_PROMPTS = [
    "An exciting, entertaining moment perfect for YouTube Shorts with a complete story arc",
    "A surprising or shocking revelation that would grab attention and keep viewers engaged",
    "A funny or humorous moment with setup and payoff that people would want to share",
    "An educational moment explaining something valuable with clear beginning and end",
    "A dramatic or intense moment with buildup and resolution perfect for short-form content"
]

# === LOGGER SETUP ===
logger = logging.getLogger("highlight_detection")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)


def transcribe_video(video_path: str) -> List[Dict]:
    logger.info("1/6 ▶ Loading Whisper model…")
    model = whisper.load_model("base")
    logger.info("2/6 ▶ Transcribing video: %s", video_path)
    result = model.transcribe(video_path, word_timestamps=False)
    segments = [
        {"start": float(s["start"]), "end": float(s["end"]), "text": s["text"].strip()}
        for s in result["segments"]
    ]
    logger.info("2/6 ✔ Transcribed %d segments", len(segments))
    return segments


def split_into_windows(segments: List[Dict]) -> List[Dict]:
    logger.info("3/6 ▶ Building %ds windows with %ds step…", WINDOW_SIZE, WINDOW_STEP)
    words = []
    for seg in segments:
        dur = seg["end"] - seg["start"]
        toks = seg["text"].split()
        if not toks:
            continue
        per_word = dur / len(toks)
        for i, w in enumerate(toks):
            words.append({"time": seg["start"] + i*per_word, "word": w})

    windows = []
    if words:
        t0, t_end = words[0]["time"], words[-1]["time"]
        start = t0
        while start < t_end:
            end = start + WINDOW_SIZE
            txt = " ".join(w["word"] for w in words if start <= w["time"] < end)
            if txt:
                windows.append({"start": start, "end": end, "text": txt})
            start += WINDOW_STEP

    logger.info("3/6 ✔ Created %d windows", len(windows))
    return windows


def score_windows(windows: List[Dict]) -> List[Dict]:
    logger.info("4/6 ▶ Scoring windows via multi-criteria embedding similarity…")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        logger.error("OPENAI_API_KEY not set")
        raise RuntimeError("Set OPENAI_API_KEY in your environment")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=key)

    # Get embeddings for all highlight prompts
    logger.info("   • Computing embeddings for %d highlight criteria…", len(HIGHLIGHT_PROMPTS))
    resp = client.embeddings.create(model=EMBED_MODEL, input=HIGHLIGHT_PROMPTS)
    proto_embs = np.array([item.embedding for item in resp.data], dtype=np.float32)
    
    # Get embeddings for all window texts
    texts = [w["text"] for w in windows]
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    text_embs = np.array([item.embedding for item in resp.data], dtype=np.float32)

    # Compute similarity to each prompt and take the maximum
    all_sims = []
    for proto in proto_embs:
        sims = (text_embs @ proto) / (np.linalg.norm(text_embs, axis=1) * np.linalg.norm(proto) + 1e-8)
        all_sims.append(sims)
    
    # Take maximum similarity across all prompts for each window
    max_sims = np.maximum.reduce(all_sims)
    
    # Add content density bonus (longer text = more content)
    text_lengths = np.array([len(w["text"]) for w in windows])
    length_scores = (text_lengths - text_lengths.min()) / (text_lengths.max() - text_lengths.min() + 1e-8)
    
    # Add narrative completeness score (look for question words, conclusions, etc.)
    narrative_scores = []
    for text in texts:
        score = 0.0
        text_lower = text.lower()
        
        # Boost for question/answer patterns (good for shorts)
        if any(word in text_lower for word in ['what', 'why', 'how', 'when', 'where', 'who']):
            score += 0.3
        if any(word in text_lower for word in ['because', 'so', 'therefore', 'result', 'answer']):
            score += 0.2
            
        # Boost for emotional words (engaging content)
        if any(word in text_lower for word in ['amazing', 'incredible', 'shocking', 'surprising', 'funny', 'hilarious']):
            score += 0.2
            
        # Boost for action words (dynamic content)
        if any(word in text_lower for word in ['look', 'watch', 'see', 'check', 'notice', 'observe']):
            score += 0.1
            
        # Boost for conclusion words (complete thoughts)
        if any(word in text_lower for word in ['finally', 'conclusion', 'result', 'end', 'turns out']):
            score += 0.2
            
        narrative_scores.append(min(score, 1.0))  # Cap at 1.0
    
    narrative_scores = np.array(narrative_scores)
    
    # Combine all scoring factors (50% similarity, 30% content, 20% narrative)
    final_scores = 0.5 * max_sims + 0.3 * length_scores + 0.2 * narrative_scores

    for w, s in zip(windows, final_scores):
        w["score"] = float(s)

    logger.info("4/6 ✔ Scoring done (scores ∈ [%.3f, %.3f])", float(final_scores.min()), float(final_scores.max()))
    return windows


def select_clips(windows: List[Dict], segments: List[Dict]) -> List[Tuple[float, float]]:
    logger.info("5/6 ▶ Selecting all quality highlights for YouTube Shorts…")
    
    if not segments:
        return []
    
    # Get total video duration
    video_duration = max(seg["end"] for seg in segments)
    logger.info("    Video duration: %.1f minutes (%.1f seconds)", video_duration / 60, video_duration)
    
    # Calculate dynamic quality threshold based on score distribution
    scores = np.array([w["score"] for w in windows])
    mean_score = scores.mean()
    std_score = scores.std()
    
    # Use a more stringent threshold for quality highlights
    quality_threshold = mean_score + 0.5 * std_score
    logger.info("    Quality threshold = mean(%.3f) + 0.5·std(%.3f) = %.3f", 
                mean_score, std_score, quality_threshold)
    
    # Filter windows above quality threshold
    quality_windows = [w for w in windows if w["score"] >= quality_threshold]
    logger.info("    Found %d high-quality windows out of %d total", len(quality_windows), len(windows))
    
    if not quality_windows:
        # If threshold is too high, use top 20% of windows
        sorted_windows = sorted(windows, key=lambda w: w["score"], reverse=True)
        quality_windows = sorted_windows[:max(1, len(windows) // 5)]
        logger.info("    Using top %d windows (20%% of total)", len(quality_windows))
    
    # Sort by score (best first) for processing
    quality_windows.sort(key=lambda w: w["score"], reverse=True)
    
    # Minimum gap between clips to ensure non-overlapping content
    min_gap_seconds = TARGET_CLIP_SECONDS * 1.2  # 48 seconds gap
    selected_clips = []
    
    logger.info("    Processing %d candidate windows...", len(quality_windows))
    
    for i, window in enumerate(quality_windows):
        window_center = (window["start"] + window["end"]) / 2
        
        # Create potential clip around this window
        clip_start = max(0.0, window_center - TARGET_CLIP_SECONDS / 2)
        clip_end = min(video_duration, clip_start + TARGET_CLIP_SECONDS)
        
        # Adjust if clip extends beyond video boundaries
        if clip_end > video_duration:
            clip_end = video_duration
            clip_start = max(0.0, clip_end - TARGET_CLIP_SECONDS)
        
        # Check for sufficient gap with existing clips
        has_sufficient_gap = True
        for existing_start, existing_end in selected_clips:
            gap_before = clip_start - existing_end
            gap_after = existing_start - clip_end
            
            # Must have sufficient gap before or after
            if not (gap_before >= min_gap_seconds or gap_after >= min_gap_seconds):
                has_sufficient_gap = False
                break
        
        if has_sufficient_gap:
            # Find transcript segments that overlap with this clip
            overlapping_segs = [seg for seg in segments 
                              if seg["end"] > clip_start and seg["start"] < clip_end]
            
            if overlapping_segs:
                # Fine-tune to complete sentences/thoughts
                seg_start = min(seg["start"] for seg in overlapping_segs)
                seg_end = max(seg["end"] for seg in overlapping_segs)
                
                # Look for natural boundaries (extend slightly for complete thoughts)
                extended_segs = [seg for seg in segments 
                               if seg["start"] >= seg_start - 3 and seg["end"] <= seg_end + 3]
                
                if extended_segs:
                    final_start = min(seg["start"] for seg in extended_segs)
                    final_end = max(seg["end"] for seg in extended_segs)
                    
                    # Ensure duration is within acceptable bounds
                    duration = final_end - final_start
                    if duration < MIN_CLIP_SECONDS:
                        # Extend symmetrically around center
                        center = (final_start + final_end) / 2
                        final_start = max(0.0, center - TARGET_CLIP_SECONDS / 2)
                        final_end = min(video_duration, final_start + TARGET_CLIP_SECONDS)
                    elif duration > MAX_CLIP_SECONDS:
                        # Keep the highest-scoring portion
                        final_end = final_start + TARGET_CLIP_SECONDS
                    
                    # Final check for overlaps (shouldn't happen with gap check above)
                    final_duration = final_end - final_start
                    if final_duration >= MIN_CLIP_SECONDS:
                        selected_clips.append((final_start, final_end))
                        logger.info("    ✅ Selected clip %d: %.1f-%.1f seconds (%.1fs, score=%.3f)", 
                                  len(selected_clips), final_start, final_end, 
                                  final_duration, window["score"])
        else:
            logger.debug("    ⏭️  Skipped window %d (insufficient gap)", i+1)
    
    # Sort clips by start time for chronological order
    selected_clips.sort(key=lambda x: x[0])
    
    logger.info("5/6 ✔ Selected %d quality highlights distributed across video:", len(selected_clips))
    
    if selected_clips:
        for i, (start, end) in enumerate(selected_clips, 1):
            start_time = f"{int(start//60):02d}:{int(start%60):02d}"
            end_time = f"{int(end//60):02d}:{int(end%60):02d}"
            logger.info("    Clip %d: %s - %s (%.1fs)", i, start_time, end_time, end - start)
        
        # Show coverage statistics
        total_clip_duration = sum(end - start for start, end in selected_clips)
        coverage_percentage = (total_clip_duration / video_duration) * 100
        logger.info("    Coverage: %.1f%% of video (%.1f minutes of clips)", 
                   coverage_percentage, total_clip_duration / 60)
    else:
        logger.warning("    No clips selected - consider lowering quality threshold")
    
    return selected_clips

def detect_highlights(video_path: str) -> List[Tuple[float, float]]:
    """
    Main function to detect highlights in a video for YouTube Shorts.
    Automatically finds all quality highlights without artificial limits.
    
    Args:
        video_path: Path to the video file
    
    Returns:
        List of (start_time, end_time) tuples for each highlight clip
    """
    logger.info("🎬 Starting intelligent highlight detection for: %s", video_path)
    
    # Step 1: Transcribe video
    segments = transcribe_video(video_path)
    if not segments:
        logger.warning("No transcript segments found")
        return []
    
    # Step 2: Create sliding windows
    windows = split_into_windows(segments)
    if not windows:
        logger.warning("No windows created from segments")
        return []
    
    # Step 3: Score windows
    scored_windows = score_windows(windows)
    
    # Step 4: Select all quality clips (no artificial limit)
    highlights = select_clips(scored_windows, segments)
    
    logger.info("🎉 Intelligent highlight detection complete! Found %d quality clips", len(highlights))
    return highlights


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Intelligently detect highlights in video for YouTube Shorts")
    parser.add_argument("video_path", help="Path to the video file")
    parser.add_argument("--output-dir", help="Directory to save clips (optional)")
    parser.add_argument("--channel", help="Channel name for logo overlay (optional)")
    parser.add_argument("--quality-threshold", type=float, help="Custom quality threshold multiplier (default: 0.5)")
    args = parser.parse_args()

    try:
        # Detect highlights automatically based on content quality
        highlights = detect_highlights(args.video_path)
        
        if not highlights:
            print("❌ No quality highlights detected")
            print("💡 Try a video with more varied or engaging content")
            sys.exit(1)
        
        print(f"\n✅ Found {len(highlights)} quality highlights:")
        total_duration = 0
        for i, (start, end) in enumerate(highlights, 1):
            duration = end - start
            total_duration += duration
            start_time = f"{int(start//60):02d}:{int(start%60):02d}"
            end_time = f"{int(end//60):02d}:{int(end%60):02d}"
            print(f"  {i:2d}. {start_time} → {end_time} ({duration:4.1f}s)")
        
        print(f"\n📊 Total highlight content: {total_duration/60:.1f} minutes")
        
        # Optionally create clips
        if args.output_dir:
            from pathlib import Path
            output_dir = Path(args.output_dir)
            output_dir.mkdir(exist_ok=True)
            
            print(f"\n🎬 Creating {len(highlights)} clips in {output_dir}...")
            video_id = Path(args.video_path).stem
            
            # Convert highlights to the format expected by make_clips
            highlight_dicts = [{"start": start, "end": end} for start, end in highlights]
            
            try:
                clips = make_clips(
                    args.video_path,
                    highlight_dicts,
                    video_id=video_id,
                    channel=args.channel,  # Use specified channel or None for no logo
                    remove_voice=False
                )
                print(f"✅ Created {len(clips)} clip files")
                for i, clip in enumerate(clips, 1):
                    print(f"   📁 {i:2d}. {Path(clip).name}")
            except Exception as e:
                logger.error("Failed to create clips: %s", e)
        
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception("Highlight detection failed: %s", e)
        sys.exit(1)
