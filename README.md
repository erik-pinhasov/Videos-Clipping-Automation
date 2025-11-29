# YouTube Videos Clipping Automation

A Python automation tool I built to streamline content distribution across multiple platforms. It downloads Creative Commons videos from YouTube, adds branding, and automatically creates short-form content for YouTube Shorts while uploading full videos to Rumble.

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI-412991.svg)](https://openai.com/)


## What It Does

This project automates the entire workflow of repurposing long-form YouTube content into engaging short clips:

- Finds Creative Commons videos from specified YouTube channels
- Downloads videos in the highest available quality
- Adds custom logo watermarks with configurable positioning
- Analyzes videos using AI to identify the most engaging moments
- Creates 60-second vertical clips optimized for YouTube Shorts
- Generates subtitles automatically using OpenAI's Whisper
- Creates optimized titles, descriptions, and tags for better reach
- Uploads full videos to Rumble and clips to YouTube Shorts
- Keeps track of processed videos to avoid duplicates

The system handles retries, manages API quotas, and logs everything for debugging. I built it to be configurable through environment variables so you can adapt it to your needs without changing code.

## How It Works

The pipeline processes videos in this order:

1. **Download** → Grabs videos from YouTube channels using yt-dlp
2. **Brand** → Adds your logo overlay using FFmpeg
3. **Split** → Full video goes to Rumble, then we create clips
4. **Analyze** → AI identifies engaging moments for short clips
5. **Generate** → Creates 60-second vertical clips with subtitles
6. **Optimize** → AI writes catchy titles and descriptions
7. **Upload** → Clips go to YouTube Shorts, full video to Rumble
8. **Track** → Saves progress to avoid reprocessing videos

## 🏗️ Pipeline Flow

```
┌─────────────────┐
│  YouTube        │
│  (CC Videos)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Download       │
│  & Filter       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Add Logo       │
│  Watermark      │
└────────┬────────┘
         │
         ├──────────────────┬───────────────┐
         ▼                  ▼               ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
│   Rumble        │  │  AI Analyze  │  │  Generate    │
│ (Full Video)    │  │  Highlights  │  │  Metadata    │
└─────────────────┘  └──────┬───────┘  └──────────────┘
                            ▼
                     ┌──────────────┐
                     │  Create 60s  │
                     │  Clips       │
                     └──────┬───────┘
                            ▼
                     ┌──────────────┐
                     │  Add AI      │
                     │  Subtitles   │
                     └──────┬───────┘
                            ▼
                     ┌──────────────┐
                     │  YouTube     │
                     │  Shorts      │
                     └──────────────┘
```

## What You'll Need

Before running this, make sure you have:

**Software:**
- Python 3.9 or newer
- FFmpeg installed and added to your PATH ([download here](https://ffmpeg.org/download.html))

**API Access:**
- YouTube Data API v3 credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- OpenAI API key from [platform.openai.com](https://platform.openai.com/api-keys)
- A Rumble account for uploading videos

**Optional:**
- Vosk for local transcription instead of OpenAI Whisper (saves API costs)

## Installation

**1. Clone and setup:**
```bash
git clone https://github.com/yourusername/youtube-rumble-automation.git
cd youtube-rumble-automation

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

**2. Configure your environment:**
```bash
cp .env.example .env
# Edit .env and add your API keys and credentials
```

**3. Set up YouTube OAuth:**
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a project and enable YouTube Data API v3
- Create OAuth 2.0 credentials and download the JSON file
- Save it as `credentials/client_secret.json`

**4. Add your logo:**

Put your logo in `media/assets/logo.png` (or specify a custom path in `.env`)

**5. Configure channels to monitor:**

Edit `.env` and add the YouTube channels you want to process:
```env
YOUTUBE_CHANNELS_JSON={"channel1": "https://www.youtube.com/@channel1/videos"}
```

**6. Run it:**
```bash
python main.py
```

The first run will ask you to authenticate with YouTube via OAuth. After that, it runs automatically.

## Configuration

All settings are in `.env`. Here are the important ones:

**Required API keys and Rumble credentials:**
```env
YOUTUBE_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
RUMBLE_EMAIL=your@email.com
RUMBLE_PASSWORD=your_password
```

## AI Features

Integrated OpenAI's APIs for the intelligent parts:

**Highlight Detection:** The system analyzes video transcripts to find the most engaging moments. It looks for action, emotion, and interesting events rather than just random clips.

**Subtitles:** Whisper API transcribes the audio with accurate timing. The subtitles are formatted specifically for YouTube Shorts with bold text and positioning.

**Metadata:** GPT-3.5 generates catchy titles, descriptions, and tags. I tuned the prompts to avoid generic titles and create content that actually performs well.


## Important Notes

**Legal stuff:**
- Only use this with Creative Commons licensed content
- Make sure you have the rights to upload and repurpose the videos
- Respect YouTube and Rumble's terms of service
- I'm not responsible for how you use this tool


## Built With

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloading
- [OpenAI API](https://openai.com/) - AI features
- [FFmpeg](https://ffmpeg.org/) - Video processing
- [Playwright](https://playwright.dev/) - Browser automation
- [Google YouTube API](https://developers.google.com/youtube/v3) - Video uploads

---

## Disclaimer

This is a personal project I built for automating content workflows. Use it responsibly and respect copyright laws. Make sure you have the necessary rights to any content you process.

