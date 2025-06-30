import os
import logging
import requests
import json
import openai
from config import HF_API_TOKEN

logger = logging.getLogger(__name__)

# Hugging Face model for metadata generation
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3-7b-instruct")


def generate_metadata(clip_path: str) -> dict:

    logger.info("Transcribing clip for metadata: %s", clip_path)
    with open(clip_path, "rb") as audio_file:
        transcript_res = openai.Audio.transcribe("whisper-1", audio_file)

    segments = transcript_res.get("segments", [])
    transcript_text = " ".join(seg.get("text", "").strip() for seg in segments)
    logger.info("Transcript for metadata: %s", transcript_text[:100] + "...")

    prompt = (
        "Generate a JSON object with the following keys:\n"
        "1. title: A 5-word catchy headline for a YouTube Short.\n"
        "2. description: A 1-2 sentence summary.\n"
        "3. hashtags: A JSON list of 3-5 relevant hashtags (each starting with #).\n"
        "Return only valid JSON.\n"
        f"Transcript: \"{transcript_text}\""
    )

    logger.info("Requesting metadata generation from HF model %s", HF_MODEL)
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 150, "temperature": 0.7},
    }
    response = requests.post(
        f"https://api-inference.huggingface.co/models/{HF_MODEL}",
        headers=headers,
        json=payload,
    )
    response.raise_for_status()
    output = response.json()

    if isinstance(output, list) and output and "generated_text" in output[0]:
        gen_text = output[0]["generated_text"]
    else:
        gen_text = output.get("generated_text", str(output))

    try:
        metadata = json.loads(gen_text)
    except json.JSONDecodeError:
        start = gen_text.find("{")
        end = gen_text.rfind("}") + 1
        metadata = json.loads(gen_text[start:end])
    
    logger.info("Generated metadata: %s", metadata)
    return metadata
