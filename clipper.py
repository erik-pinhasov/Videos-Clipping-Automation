import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any

import config

def get_video_size(path: str) -> Tuple[int,int]:
    """Return the (width, height) of a video using ffprobe."""
    out = subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=p=0', path
    ], stderr=subprocess.DEVNULL).decode().strip()
    w, h = out.split(',')
    return int(w), int(h)

def overlay_logo(input_path: str, output_path: str, channel: str) -> None:
    """
    Overlay your logo for `channel` by centering a 10%-oversized version
    over the old watermark box from config.
    """
    # Probe actual video size
    video_w, video_h = get_video_size(input_path)

    ch = config.CHANNEL_LOGOS[channel]
    logo_def = config.LOGO_DEFINITIONS[ch['shape']]
    native_w, native_h = logo_def['native']

    # Compute old watermark box (orig_w × orig_h) and top-left (x0,y0)
    orig_w = ch['total_w'] - ch['spacing_x']
    orig_h = ch['total_h'] - ch['spacing_y']

    if 'left' in ch['location']:
        x0 = ch['spacing_x']
    else:
        # right edge of watermark box is (video_w - spacing_x),
        # so left edge = that minus orig_w
        x0 = (video_w - ch['spacing_x']) - orig_w

    if 'top' in ch['location']:
        y0 = ch['spacing_y']
    else:
        y0 = (video_h - ch['spacing_y']) - orig_h

    # Compute scale factor (never downscale, then +10%)
    scale_w = orig_w / native_w if orig_w > native_w else 1.0
    scale_h = orig_h / native_h if orig_h > native_h else 1.0
    scale    = max(scale_w, scale_h)
    out_w   = int(native_w * scale)
    out_h   = int(native_h * scale)

    x_pos = int(x0 + (orig_w - out_w)  / 2)
    y_pos = int(y0 + (orig_h - out_h)  / 2)

    # Run ffmpeg in one pass
    fc = (
        f"[1:v]scale={out_w}:{out_h}[logo];"
        f"[0:v][logo]overlay={x_pos}:{y_pos}"
    )
    subprocess.run([
        'ffmpeg', '-y',
        '-i', input_path,
        '-i', str(logo_def['path']),
        '-filter_complex', fc,
        '-c:a', 'copy',
        output_path
    ], check=True)

def make_clips(
    input_path: str,
    highlights: List[Dict[str, Any]],
    video_id: str,
    channel: str
) -> List[str]:
    """
    For each highlight (with 'start' and 'end'), trim then overlay your logo.
    """
    Path(config.CLIPS_DIR).mkdir(exist_ok=True)
    outputs: List[str] = []

    for idx, seg in enumerate(highlights):
        tmp = Path(config.CLIPS_DIR) / f"{video_id}_{idx}_tmp.mp4"
        out = Path(config.CLIPS_DIR) / f"{video_id}_{idx}.mp4"

        # Trim
        subprocess.run([
            'ffmpeg', '-y',
            '-ss', str(seg['start']),
            '-to', str(seg['end']),
            '-i', input_path,
            '-c', 'copy',
            str(tmp)
        ], check=True)

        # Overlay
        overlay_logo(str(tmp), str(out), channel)
        tmp.unlink()
        outputs.append(str(out))

    return outputs
