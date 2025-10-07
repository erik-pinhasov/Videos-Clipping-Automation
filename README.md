# YouTube & Rumble Shorts Automation

This project automates downloading long nature videos, creating wildlife highlight Shorts, and uploading them to YouTube and Rumble.

## Rumble upload: simple direct flow

By default, the uploader now uses a simple and deterministic browser flow for Rumble:

- Login to Rumble
- Navigate directly to https://rumble.com/upload.php
- Attach the video to the hidden input with id `#Filedata`
- Fill title, description, tags
- Set categories (Primary: Entertainment, Secondary: Wild Wildlife)
- Select the first generated thumbnail
- Click Upload, pick licensing “Rumble Only”, accept rights/terms, and Final Submit

You can control this with the environment variable:

- `RUMBLE_SIMPLE_FLOW=true` (default): Use the direct navigation to `upload.php`
- `RUMBLE_SIMPLE_FLOW=false`: Use the more robust fallback flow if needed

Other related settings (with defaults) are defined in `config.py` and can be set via environment variables:

- `RUMBLE_UPLOAD_METHOD=playwright` (recommended)
- `PLAYWRIGHT_HEADLESS=false` to see the browser while debugging
- `RUMBLE_UPLOAD_TIMEOUT_MS=10800000` (3 hours)

## Title and metadata behavior

Metadata is generated via OpenAI and avoids reusing the original YouTube title by default:

- `METADATA_USE_ORIGINAL_TITLE=false` (default): Generate a fresh title for each Short
- `METADATA_FALLBACK_TITLE="Wildlife Highlight"`: Safe fallback if generation fails
- `YOUTUBE_FORCE_SHORTS_HASHTAG=true`: Appends `#shorts` to titles if missing

## Quick start

1) Set environment variables in a `.env` file (see keys in `config.py`):

- OPENAI_API_KEY
- YOUTUBE_API_KEY
- YOUTUBE_CLIENT_SECRET_FILE
- RUMBLE_USERNAME, RUMBLE_EMAIL, RUMBLE_PASSWORD

2) Run the main automation:

```powershell
python .\main.py
```

3) Test Rumble upload flow with a specific clip:

```powershell
python .\scripts\rumble_upload_test.py
```

If you see the browser fail to attach the file, keep `RUMBLE_SIMPLE_FLOW=true` and ensure the input `#Filedata` exists on your upload page variant. The uploader verifies that `#Filedata.files.length > 0` after selection.

