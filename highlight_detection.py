import logging
from typing import List, Tuple, Dict
import openai
import json

logger = logging.getLogger(__name__)

def select_highlight_clips(
    transcript: List[Dict],
    clip_duration: int = 20,
    num_clips: int = 15,
    num_candidates: int = 30
) -> List[Tuple[float, float]]:
    """
    Select highlight clips by choosing transcript segments with the most content,
    scoring them via GPT, and returning top non-overlapping time windows.

    Args:
        transcript: List of {'start': float, 'end': float, 'text': str} segments
        clip_duration: Desired clip length in seconds (default 20)
        num_clips: Number of highlight clips to return (default 15)
        num_candidates: How many top segments to consider by text length (default 30)

    Returns:
        List of (start_time, end_time) tuples for each selected clip
    """
    # 1. Heuristic candidate selection by text length
    candidates = sorted(
        transcript,
        key=lambda seg: len(seg["text"]),
        reverse=True
    )[:num_candidates]

    # 2. Build fixed-duration windows around each candidate
    windows = []
    for seg in candidates:
        start = max(0.0, seg["start"] - clip_duration / 2)
        end = start + clip_duration
        windows.append({"start": start, "end": end, "text": seg["text"]})

    # 3. Batch-scoring prompt
    prompt = (
        "Rate each of these transcript snippets for how attention-grabbing they are "
        "on a scale from 1 to 10. Return a JSON list of numbers in order.\n"
    )
    for idx, win in enumerate(windows):
        snippet = win["text"].replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        prompt += f"{idx+1}. {snippet}\n"

    logger.info("Sending GPT scoring prompt with %d candidates", len(windows))
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=num_candidates * 5 + 50
    )
    content = response.choices[0].message.content

    # 4. Parse scores
    try:
        scores = json.loads(content)
    except json.JSONDecodeError:
        scores = []
        for part in content.replace("[", "").replace("]", "").split(","):  # fallback
            try:
                scores.append(int(part.strip()))
            except:
                continue
    logger.info("Received %d scores", len(scores))

    # 5. Pair, sort, and pick non-overlapping top clips
    scored_windows = sorted(
        zip(windows, scores), key=lambda x: x[1], reverse=True
    )
    selected: List[Tuple[float, float]] = []
    for win, score in scored_windows:
        s, e = win["start"], win["end"]
        # reject if overlaps any already selected
        if any(abs(s - ps) < clip_duration for ps, pe in selected):
            continue
        selected.append((s, e))
        if len(selected) >= num_clips:
            break

    logger.info("Selected %d highlight clips", len(selected))
    return selected
