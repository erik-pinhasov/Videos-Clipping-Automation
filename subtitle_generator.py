import os
import re
from typing import List, Dict
import openai
import config
import argparse
import logging
openai.api_key = config.OPENAI_API_KEY

# use the v1 client
client = openai.OpenAI()

def describe_clips(highlights: List[Dict], segments: List[Dict]) -> List[str]:
    # build clip sections
    sections = []
    for idx, clip in enumerate(highlights, start=1):
        start, end = clip["start"], clip["end"]
        text = " ".join(
            seg["text"]
            for seg in segments
            if seg["start"] >= start and seg["end"] <= end
        ).strip()
        sections.append(f"Clip {idx} ({start:.1f}s–{end:.1f}s): {text}")

    prompt = (
        "You are a documentary narrator. For each of the following clips, "
        "write a concise but vivid narration describing exactly what the "
        "viewer sees and hears—play-by-play of the action.\n\n"
        + "\n".join(sections)
    )

    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a documentary narrator."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.7,
        max_tokens=len(highlights) * 150
    )

    full = resp.choices[0].message.content.strip()
    pattern = r"(Clip \d+ \(\d+\.\d+s–\d+\.\d+s\):[\s\S]*?)(?=Clip \d+ \(|\Z)"
    return [m.strip() for m in re.findall(pattern, full)]


def synthesize_speech(scripts: List[str], out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    audio_paths: List[str] = []
    for i, text in enumerate(scripts):
        resp = client.audio.speech.create(
            model=config.TTS_MODEL,
            voice=config.TTS_VOICE,
            input=text
        )
        path = os.path.join(out_dir, f"clip_{i}.mp3")
        with open(path, "wb") as f:
            f.write(resp.audio)
        audio_paths.append(path)
    return audio_paths


def write_srt(clips: List[Dict], transcript: List[Dict], out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    srt_paths: List[str] = []

    def fmt(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    for i, clip in enumerate(clips):
        entries = []
        n = 1
        for seg in transcript:
            if seg["start"] < clip["end"] and seg["end"] > clip["start"]:
                st = seg["start"] - clip["start"]
                et = seg["end"]   - clip["start"]
                entries.append((n, st, et, seg["text"]))
                n += 1

        lines: List[str] = []
        for num, st, et, txt in entries:
            lines += [
                str(num),
                f"{fmt(st)} --> {fmt(et)}",
                txt,
                ""
            ]

        path = os.path.join(out_dir, f"clip_{i}.srt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        srt_paths.append(path)

    return srt_paths


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Smoke-test subtitle_generator pipeline"
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Skip TTS synthesis step"
    )
    parser.add_argument(
        "--skip-srt",
        action="store_true",
        help="Skip SRT writing step"
    )
    args = parser.parse_args()

    # --- Dummy data for quick tests ---
    segments = [
        {"start": 0.0, "end": 1.0, "text": "The quick brown fox"},
        {"start": 1.0, "end": 2.0, "text": "jumps over the lazy dog"}
    ]
    highlights = [{"start": 0.0, "end": 2.0}]

    # 1) describe_clips
    print("\n== Testing describe_clips ==")
    try:
        scripts = describe_clips(highlights, segments)  # :contentReference[oaicite:0]{index=0}
        for i, s in enumerate(scripts):
            print(f"Script {i+1}: {s}\n")
    except Exception:
        logging.exception("describe_clips failed")

    # 2) synthesize_speech
    if not args.skip_tts:
        print("\n== Testing synthesize_speech ==")
        try:
            audio_files = synthesize_speech(scripts, out_dir="test_audio")
            print("Generated audio files:", audio_files)
        except Exception:
            logging.exception("synthesize_speech failed")

    # 3) write_srt
    if not args.skip_srt:
        print("\n== Testing write_srt ==")
        try:
            srt_files = write_srt(highlights, segments, out_dir="test_srt")
            print("Generated SRT files:", srt_files)
        except Exception:
            logging.exception("write_srt failed")

    print("\n== All subtitle_generator tests completed ==\n")
