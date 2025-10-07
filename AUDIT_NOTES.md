Project audit on 2025-10-07

Summary
- Relying on OpenAI only; removed Hugging Face usage and token requirement.
- Rumble upload via Playwright fixed; auto-installs Chromium if missing.
- Shorts: clips now output 1080x1920 with blurred background; titles append #shorts (configurable); YouTube madeForKids flag added.
- Subtitles: exact narrator mode via Whisper segments (configurable), or disabled to save tokens.
- Cleanup: clips deleted after successful upload; branded/original files optionally deleted; source marked used when all shorts succeed.

Potentially unnecessary or unused files/deps
- src/services/youtube_api.py: not referenced in current orchestration (content sourcing uses ContentManager + yt-dlp). Keep only if you plan to switch to Data API.
- src/services/downloader.py: there is a simpler downloader path in VideoProcessor using yt_dlp directly. This downloader class duplicates functionality and includes a duplicated class definition in file (needs cleanup or removal).
- requirements.txt:
  - moviepy, Pillow, librosa, soundfile, psutil appear unused in the current code paths; consider removing to shrink environment.
- Logs and state files: automation_state.json, processing_checkpoint.json (legacy), openai_usage.json; remove if not used by your monitoring.

Code hygiene findings
- src/services/downloader.py: the file contains two duplicated implementations of VideoDownloader in the same file; should consolidate into a single class or remove the file if not used.
- src/services/youtube_api.py: wrapper for YouTube Data API; not used by main pipeline. If unused, delete to reduce confusion.
- src/services/highlight_detector.py: now only local analysis; looks consistent. Fallback generator ensures many clips for long videos.
- src/services/clip_creator.py: includes vertical 9:16 formatting and subtitle filter fix; added debug log for FFmpeg filter.

Recommended next steps
1) Remove unused dependencies from requirements.txt (moviepy, Pillow, librosa, soundfile, psutil) unless you plan to use them.
2) Delete src/services/downloader.py or refactor to one class and use it from VideoProcessor; right now, VideoProcessor downloads via yt_dlp inline.
3) Delete src/services/youtube_api.py if you are not using Data API discovery.
4) Delete legacy files: automation_state.json, processing_checkpoint.json, openai_usage.json if not part of your current flow.
5) Add retry/backoff for YouTube clip uploads to improve the success ratio on larger batches.
6) Add per-run cap (max_shorts_per_video) to avoid 40+ uploads in one go if you want to throttle.

Config flags reference (.env)
- SUBTITLES_MODE=exact|off
- WHISPER_MODEL=whisper-1
- YOUTUBE_MADE_FOR_KIDS=true|false
- YOUTUBE_FORCE_SHORTS_HASHTAG=true|false
- DELETE_CLIP_AFTER_UPLOAD=true|false
- CLEANUP_DELETE_BRANDED=true|false
- CLEANUP_DELETE_ORIGINAL_DOWNLOAD=true|false
- RUMBLE_UPLOAD_METHOD=playwright
- PLAYWRIGHT_AUTO_INSTALL=true|false
- PLAYWRIGHT_HEADLESS=false|true
- RUMBLE_UPLOAD_TIMEOUT_MS=3600000

