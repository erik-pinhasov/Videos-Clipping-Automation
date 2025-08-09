import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Any
import json
import config


def get_video_size(path: str) -> Tuple[int, int]:
    """Return the (width, height) of a video using ffprobe."""
    out = subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=p=0', path
    ], stderr=subprocess.DEVNULL).decode().strip()
    w, h = out.split(',')
    return int(w), int(h)


def get_video_specs(path: str) -> dict:
    """
    Returns the video stream's bit_rate (in bps) and fps (float).
    """
    out = subprocess.check_output([
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams', path
    ])
    info = json.loads(out)
    for st in info.get('streams', []):
        if st.get('codec_type') == 'video':
            bps = int(st.get('bit_rate', 0))
            num, den = st.get('r_frame_rate', '0/1').split('/')
            fps = (float(num) / float(den)) if den and float(den) else None
            return {'bit_rate': bps, 'fps': fps}
    return {'bit_rate': 0, 'fps': None}

def overlay_logo(input_path: str, output_path: str, channel: str) -> None:
    """
    Overlays a pre-sized logo for the specified channel at the configured position.
    Logo files should be in assets/ folder named "logo_{channel}.png"
    """
    # 1) Get the logo file path
    logo_path = Path("assets") / f"logo_{channel}.png"
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo file not found: {logo_path}")

    # 2) Get video dimensions
    video_w, video_h = get_video_size(input_path)
    
    # 3) Get channel configuration
    if channel not in config.CHANNEL_LOGOS:
        raise ValueError(f"Channel '{channel}' not found in CHANNEL_LOGOS configuration")
    
    ch = config.CHANNEL_LOGOS[channel]
    location = ch['location']
    spacing_x = ch['spacing_x']
    spacing_y = ch['spacing_y']

    # 4) Calculate position based on location
    if 'left' in location:
        x_pos = spacing_x
    else:  # right
        # We'll get logo dimensions and subtract from video width
        logo_w, logo_h = get_video_size(str(logo_path))
        x_pos = video_w - spacing_x - logo_w
    
    if 'top' in location:
        y_pos = spacing_y
    else:  # bottom
        if 'logo_w' not in locals():
            logo_w, logo_h = get_video_size(str(logo_path))
        y_pos = video_h - spacing_y - logo_h

    # 5) Ensure logo stays within bounds
    if 'logo_w' not in locals():
        logo_w, logo_h = get_video_size(str(logo_path))
    
    x_pos = max(0, min(x_pos, video_w - logo_w))
    y_pos = max(0, min(y_pos, video_h - logo_h))

    # 6) Build ffmpeg overlay filter (no scaling needed since logos are pre-sized)
    fc = f"[0:v][1:v]overlay={x_pos}:{y_pos}"

    # 7) Get original video specs for encoding
    specs = get_video_specs(input_path)
    kbps = specs['bit_rate'] // 1000 or 8000
    buf_k = kbps * 2
    fps = specs['fps']

    # 8) Run ffmpeg to overlay the logo
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-i', str(logo_path),
        '-filter_complex', fc,
        '-map', '0:a?',
        '-c:v', 'libx264',
        '-b:v', f'{kbps}k',
        '-maxrate', f'{kbps}k',
        '-bufsize', f'{buf_k}k',
        '-preset', 'superfast',
        '-threads', '0',
        '-c:a', 'copy',
    ]
    if fps:
        cmd += ['-r', str(fps)]
    cmd.append(output_path)

    subprocess.run(cmd, check=True)


def remove_narrator(input_path: str, output_path: str) -> None:
    """
    Use Demucs to separate vocals from accompaniment, then remux
    video with only the accompaniment (no narrator).
    """
    # 1) Run Demucs two-stems separation
    subprocess.run([
        'demucs', '--two-stems', input_path
    ], check=True)

    # 2) Locate Demucs output
    sep_root = Path('separated')
    if not sep_root.exists():
        raise FileNotFoundError("Demucs did not produce a 'separated' directory")
    # assume structure: separated/<model_name>/<track_stem>/no_vocals.wav
    model_dirs = list(sep_root.iterdir())
    if not model_dirs:
        raise FileNotFoundError("No model directory found under 'separated'")
    track_dir = model_dirs[0] / Path(input_path).stem
    no_vocals = track_dir / 'no_vocals.wav'
    if not no_vocals.exists():
        raise FileNotFoundError(f"No vocals-removed file at {no_vocals}")

    # 3) Remux video (copy) + no_vocals.wav
    subprocess.run([
        'ffmpeg', '-y',
        '-i', input_path,
        '-i', str(no_vocals),
        '-c:v', 'copy',
        '-map', '0:v',
        '-map', '1:a',
        '-shortest',
        output_path
    ], check=True)

    # 4) Cleanup Demucs artifacts
    shutil.rmtree(sep_root)


def make_clips(
    input_path: str,
    highlights: List[Dict[str, Any]],
    video_id: str,
    channel: str = None,
    remove_voice: bool = False
) -> List[str]:
    """
    For each highlight (with 'start' and 'end'), trim then optionally
    remove narrator, overlay your logo, and return output paths.
    """
    Path(config.CLIPS_DIR).mkdir(exist_ok=True)
    outputs: List[str] = []

    for idx, seg in enumerate(highlights):
        tmp_trim = Path(config.CLIPS_DIR) / f"{video_id}_{idx}_trim.mp4"
        tmp_clean = Path(config.CLIPS_DIR) / f"{video_id}_{idx}_clean.mp4"
        final = Path(config.CLIPS_DIR) / f"{video_id}_{idx}.mp4"

        # 1) Trim
        subprocess.run([
            'ffmpeg', '-y',
            '-ss', str(seg['start']),
            '-to', str(seg['end']),
            '-i', input_path,
            '-c', 'copy',
            str(tmp_trim)
        ], check=True)

        # 2) Remove narrator if requested
        if remove_voice:
            remove_narrator(str(tmp_trim), str(tmp_clean))
        else:
            # Remove existing file before rename
            if tmp_clean.exists():
                tmp_clean.unlink()
            tmp_trim.rename(tmp_clean)

        # 3) Overlay logo if channel provided
        if channel:
            overlay_logo(str(tmp_clean), str(final), channel)
        else:
            # Remove existing file before rename
            if final.exists():
                final.unlink()
            tmp_clean.rename(final)

        # 4) Cleanup temps
        if tmp_trim.exists():
            tmp_trim.unlink()
        if tmp_clean.exists() and tmp_clean != final:
            tmp_clean.unlink()

        outputs.append(str(final))

    return outputs

if __name__ == "__main__":
    # Example usage
    overlay_logo("C:\\Users\\erikp\\Desktop\\vscode\\youtube_short_automation\\downloads\\trim.mp4",
        "C:\\Users\\erikp\\Desktop\\vscode\\youtube_short_automation\\downloads\\trimed.mp4",
          "navwildanimaldocumentary")