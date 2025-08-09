# YouTube Shorts Automation Pipeline

Transform your content creation workflow with this automation system that discovers, processes, and publishes engaging video content across multiple platforms. This pipeline intelligently sources videos from configured YouTube channels, enhances them with custom branding, and creates optimized short-form content for maximum reach and engagement.

## 🎯 What & Why

The automation pipeline handles the complete video processing workflow from discovery to publishing. It monitors specified YouTube channels for new content, downloads suitable videos, adds your custom logo branding, generates compelling metadata using AI, uploads full videos to Rumble, creates highlight clips optimized for YouTube Shorts, and manages all temporary files automatically. The system is designed to run continuously, processing new content as it becomes available while respecting API limits and platform guidelines.

## ✨ Key Features

**Intelligent Content Discovery**
- Automated monitoring of multiple YouTube channels
- Smart filtering based on duration, upload date, and engagement metrics
- Duplicate detection to avoid reprocessing content

**Professional Video Enhancement**
- Custom logo overlay with configurable positioning
- High-quality video processing using FFmpeg
- Maintains original audio quality throughout pipeline

**AI-Powered Metadata Generation**
- Creates engaging titles and descriptions using OpenAI
- Generates relevant tags for better discoverability  
- Optimizes metadata specifically for YouTube Shorts format

**Multi-Platform Publishing**
- Automated uploads to Rumble with full video content
- YouTube Shorts creation with highlight detection
- Intelligent clip selection for maximum engagement

**Robust Operations Management**
- Detailed logging with daily rotation
- Graceful error handling with detailed diagnostics
- Automatic cleanup of temporary files
- Rate limiting to respect API quotas

## 🛠 Technology Stack

- **Python 3.8+** - Core application framework
- **yt-dlp** - Advanced video downloading capabilities
- **FFmpeg** - Professional video processing and encoding
- **OpenAI GPT** - AI-powered content metadata generation
- **Google APIs** - YouTube Data API and upload functionality
- **Selenium WebDriver** - Browser automation for Rumble uploads
- **Logging & Monitoring** - Full system observability

## 🎬 Content Strategy & Legal Considerations

### Understanding Content Rights

**⚠️ IMPORTANT LEGAL NOTICE**
This tool is designed for processing content you have rights to use. Always ensure you comply with copyright laws and platform terms of service.

### Creative Commons Content Sources

**Best Sources for Creative Commons Videos:**
- **YouTube Creative Commons**: Use YouTube's filter tools to find CC-licensed content
- **Internet Archive**: Vast collection of public domain videos
- **Wikimedia Commons**: High-quality educational and documentary content
- **Pexels Videos**: Free stock footage with permissive licenses
- **Pixabay Videos**: Large collection of royalty-free content

### Finding Creative Commons Content on YouTube

1. **Search with Filters**:
   - Go to YouTube and search for your topic (e.g., "nature documentary")
   - Click "Filters" → "Features" → "Creative Commons"
   - This shows only CC-licensed content you can legally reuse

2. **Advanced Search Tips**:
   ```
   "nature documentary" site:youtube.com "Creative Commons"
   "wildlife footage" CC license
   "scenic nature" creative commons attribution
   ```

3. **Verify Licensing**:
   - Check video description for Creative Commons license
   - Look for "Licensed to YouTube by" information
   - Verify the specific CC license type (CC BY, CC BY-SA, etc.)

### Recommended Content Niches

The pipeline works exceptionally well with these content types:

**🌿 Nature & Wildlife**
- Perfect for: Scenic landscapes, wildlife documentaries, nature sounds
- Audience: Relaxation seekers, nature enthusiasts, educational viewers
- Clip Strategy: Continuous scenic segments work best

**🎓 Educational Content**
- Perfect for: How-to videos, tutorials, documentaries
- Audience: Learners, students, professionals
- Clip Strategy: Complete explanations or key concepts

**🎵 Music & Audio**
- Perfect for: Instrumental music, ambient sounds, performances
- Audience: Music lovers, content creators needing background audio
- Clip Strategy: Musical phrases or thematic segments

**🏛️ Historical & Cultural**
- Perfect for: Historical documentaries, cultural content
- Audience: History buffs, educational content consumers
- Clip Strategy: Key historical moments or cultural highlights

**💡 Science & Technology**
- Perfect for: Science explanations, tech demos, experiments
- Audience: STEM enthusiasts, curious learners
- Clip Strategy: Complete demonstrations or key concepts

## 🎨 Logo Configuration & Branding

### Logo Design Guidelines

**Optimal Logo Specifications:**
- **Format**: PNG with transparency (recommended)
- **Size**: 150x150 to 300x300 pixels
- **Style**: Simple, readable design that works at small sizes
- **Colors**: High contrast colors that stand out on video content
- **Background**: Transparent background for clean overlay

### Logo Positioning Options

The system supports flexible logo positioning:

```python
# Example logo configurations in config.py
CHANNEL_LOGOS = {
    'your_channel_name': {
        'logo_path': 'media/assets/your_logo.png',
        'location': 'top_right',        # Position on screen
        'spacing_x': 10,                # Horizontal margin from edge
        'spacing_y': 15,                # Vertical margin from edge
        'primary_category': 'nature',    # Content category for AI
        'content_tags': ['nature', 'relaxing', 'scenic']  # Default tags
    }
}
```

**Available Positions:**
- `top_left`: Upper left corner
- `top_right`: Upper right corner (most common)
- `bottom_left`: Lower left corner
- `bottom_right`: Lower right corner
- `center`: Center of video (use sparingly)

### Creating Effective Channel Branding

**Logo Design Tips:**
1. **Keep it Simple**: Complex logos become unreadable when small
2. **High Contrast**: Ensure logo stands out against video background
3. **Brand Consistency**: Use consistent colors and fonts across channels
4. **Size Testing**: Test logo at actual overlay size before finalizing

**Channel-Specific Branding:**
```python
# Example: Different logos for different content types
CHANNEL_LOGOS = {
    'nature_channel': {
        'logo_path': 'media/assets/nature_logo.png',
        'location': 'top_right',
        'spacing_x': 20,
        'spacing_y': 20,
        'primary_category': 'nature',
        'content_tags': ['nature', 'wildlife', 'scenic', 'relaxing']
    },
    'tech_channel': {
        'logo_path': 'media/assets/tech_logo.png',
        'location': 'bottom_right',
        'spacing_x': 15,
        'spacing_y': 15,
        'primary_category': 'technology',
        'content_tags': ['tech', 'innovation', 'tutorial', 'review']
    }
}
```

## ⚙️ Dynamic Configuration System

### Content-Aware Processing

The system adapts its behavior based on your content type and channel configuration:

**Metadata Generation:**
- AI prompts adapt to your content category
- Tags are generated based on your niche
- Titles follow patterns optimized for your audience

**Highlight Detection:**
- Different strategies for different content types
- Nature content uses continuous segments
- Educational content preserves complete explanations
- Action content uses shorter, dynamic clips

### Customizing for Your Niche

**Step 1: Define Your Content Categories**
```python
# In config.py
CONTENT_CATEGORIES = [
    "your_niche_1",     # e.g., "cooking"
    "your_niche_2",     # e.g., "fitness" 
    "your_niche_3",     # e.g., "travel"
]
```

**Step 2: Create Content Templates**
```python
DEFAULT_TITLE_TEMPLATES = [
    "Amazing {category} Content",
    "Best {category} Moments",
    "Ultimate {category} Guide"
]

DEFAULT_DESCRIPTION_TEMPLATE = """
🎬 Incredible {category} content for you!

👍 Like if you enjoyed this {category} video
🔔 Subscribe for more {category} content
💬 Comment your thoughts below

#{category} #amazing #viral #shorts
""".strip()
```

**Step 3: Configure Channel-Specific Settings**
```python
CHANNEL_LOGOS = {
    'your_channel': {
        'logo_path': 'media/assets/your_logo.png',
        'location': 'top_right',
        'spacing_x': 10,
        'spacing_y': 10,
        'primary_category': 'your_main_niche',  # Used for AI context
        'content_tags': ['niche_tag1', 'niche_tag2', 'niche_tag3']
    }
}
```

### Content Strategy Examples

**🍳 Cooking Channel Example:**
```python
'cooking_channel': {
    'logo_path': 'media/assets/cooking_logo.png',
    'location': 'top_left',
    'primary_category': 'cooking',
    'content_tags': ['cooking', 'recipe', 'food', 'kitchen', 'chef']
}

CONTENT_CATEGORIES = ["cooking", "recipe", "food", "culinary"]
DEFAULT_TITLE_TEMPLATES = [
    "Delicious {category} Recipe",
    "Easy {category} Tutorial", 
    "Amazing {category} Technique"
]
```

**🎮 Gaming Channel Example:**
```python
'gaming_channel': {
    'logo_path': 'media/assets/gaming_logo.png',
    'location': 'bottom_right',
    'primary_category': 'gaming',
    'content_tags': ['gaming', 'gameplay', 'tutorial', 'tips']
}

CONTENT_CATEGORIES = ["gaming", "esports", "tutorial", "review"]
DEFAULT_TITLE_TEMPLATES = [
    "Epic {category} Moments",
    "Pro {category} Tips",
    "Best {category} Highlights"
]
```

## 📋 Prerequisites

Before installation, ensure you have the following installed on your system:

- Python 3.8 or higher
- FFmpeg (for video processing)
- Chrome/Chromium browser (for Rumble uploads)
- Git (for cloning the repository)

## 🚀 Complete Setup Guide

### Step 1: Clone and Install

```bash
# Clone the repository
git clone <your-repository-url>
cd youtube_short_automation

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Install FFmpeg

**Windows:**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract to C:\ffmpeg
3. Add C:\ffmpeg\bin to your system PATH
4. Verify installation: `ffmpeg -version`

**macOS:**
```bash
# Using Homebrew
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

### Step 3: Configure Google APIs (YouTube)

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing one
   - Enable YouTube Data API v3

2. **Create OAuth 2.0 Credentials**
   - Navigate to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client IDs"
   - Choose "Desktop Application"
   - Download the credentials JSON file
   - Rename it to `credentials.json` and place in project root

3. **Set YouTube API Quotas**
   - Note your daily quota limits (default: 10,000 units)
   - Adjust `YOUTUBE_API_DAILY_QUOTA` in config.py accordingly

### Step 4: Configure OpenAI API

1. **Get OpenAI API Key**
   - Visit [OpenAI Platform](https://platform.openai.com/)
   - Create account or sign in
   - Navigate to API Keys section
   - Create new secret key
   - Copy the key (starts with `sk-`)

2. **Set Up Billing**
   - Add payment method to your OpenAI account
   - Monitor usage at https://platform.openai.com/usage

### Step 5: Configure Hugging Face (Optional)

1. **Create Hugging Face Account**
   - Sign up at https://huggingface.co/
   - Go to Settings → Access Tokens
   - Create new token with read permissions
   - Copy the token (starts with `hf_`)

### Step 6: Set Up Rumble Account

1. **Create Rumble Creator Account**
   - Sign up at https://rumble.com/
   - Verify your account and enable creator features
   - Note your login credentials

### Step 7: Configure Environment Variables

Create `.env` file in project root:

```env
# Required API Keys
OPENAI_API_KEY=sk-your-openai-key-here
YOUTUBE_API_KEY=AIzaSy-your-youtube-api-key-here

# Rumble Credentials
RUMBLE_EMAIL=your-rumble-email@example.com
RUMBLE_PASSWORD=your-rumble-password

# Optional
HF_API_TOKEN=hf_your-hugging-face-token
```

### Step 8: Prepare Channel Assets and Configuration

1. **Create Logo Files**
   - Design logos for each channel (PNG format recommended)
   - Size: 150x150 to 300x300 pixels
   - Use transparent backgrounds
   - Save in `media/assets/` directory

2. **Update Channel Configuration**
   - Edit `config.py` CHANNEL_LOGOS section
   - Set correct logo paths and positioning
   - Configure content categories and tags
   - Customize metadata templates for your niche

**Example Configuration Setup:**
```python
# In config.py - customize for your content
CONTENT_CATEGORIES = [
    "your_niche",        # Replace with your content type
    "your_category",     # Add your categories
    "your_topic"         # Add relevant topics
]

CHANNEL_LOGOS = {
    'your_channel_name': {  # Replace with your channel name
        'logo_path': 'media/assets/your_logo.png',  # Your logo file
        'location': 'top_right',                    # Positioning
        'spacing_x': 15,                            # Adjust spacing
        'spacing_y': 20,                            # Adjust spacing  
        'primary_category': 'your_niche',           # Your content type
        'content_tags': ['tag1', 'tag2', 'tag3']   # Your tags
    }
}
```

### Step 9: Directory Structure Setup

The application will create necessary directories automatically, but you can create them manually:

```
youtube_short_automation/
├── media/
│   ├── assets/          # Logo files (your branded logos)
│   ├── downloads/       # Downloaded videos (temp)
│   ├── clips/          # Generated clips (temp)
│   └── audio/          # Audio files (temp)
├── logs/               # Application logs
├── credentials/        # API tokens and secrets
└── src/               # Application source code
```

### Step 10: Test Your Configuration

```bash
# Run configuration validation
python -c "import config; print('✓ Config OK' if config.Config().validate() else '✗ Config Error')"

# Test YouTube API connection
python -c "from src.services.youtube_api import YouTubeAPI; import config; api = YouTubeAPI(config.Config()); print('✓ YouTube API OK')"

# Test OpenAI API
python -c "import openai; import config; openai.api_key = config.Config().OPENAI_API_KEY; print('✓ OpenAI API OK')"

# List your configured channels
python -c "import config; print('Configured channels:', list(config.Config().CHANNEL_LOGOS.keys()))"
```

## 🎮 Usage

### Basic Operation

```bash
# Start the automation pipeline
python main.py

# Run with debug logging
python main.py --log-level DEBUG

# Stop gracefully with Ctrl+C
```

### Testing Single Videos

Test your configuration with individual videos before running the full pipeline:

```bash
# Test with YouTube URL
python src/utils/test_video.py --url "https://youtube.com/watch?v=VIDEO_ID" --channel "your_channel"

# Test with local file
python src/utils/test_video.py --file "path/to/video.mp4" --channel "your_channel"

# List available channels
python src/utils/test_video.py --list-channels
```

### Configuration Customization

Edit `config.py` to customize:

- **Content Categories**: Define your content niches
- **Channel Settings**: Add/remove channels and configure branding
- **Video Filtering**: Adjust duration limits, age restrictions
- **Processing Settings**: Change clip lengths, maximum clips per video
- **API Limits**: Set daily quotas and rate limiting
- **Metadata Templates**: Customize titles and descriptions for your niche

### Monitoring and Logs

- **Daily Logs**: Check `logs/automation_YYYY-MM-DD.log`
- **Real-time Monitoring**: Watch console output during operation
- **Error Tracking**: Failed operations logged with full context

## 📊 Performance Optimization

**API Efficiency**
- Implements intelligent rate limiting
- Batches API calls when possible
- Caches frequently accessed data

**Resource Management**
- Automatic cleanup of temporary files
- Configurable storage limits
- Memory-efficient video processing

**Error Recovery**
- Graceful handling of network interruptions
- Automatic retry logic with exponential backoff
- Detailed error logging for troubleshooting

## 🔧 Troubleshooting

**Common Issues:**

1. **FFmpeg Not Found**
   - Ensure FFmpeg is installed and in system PATH
   - Test with `ffmpeg -version`

2. **YouTube API Quota Exceeded**
   - Check quota usage in Google Cloud Console
   - Reduce `MAX_VIDEOS_PER_CHANNEL` in config
   - Wait for quota reset (daily)

3. **OpenAI API Errors**
   - Verify API key is correct and active
   - Check account billing and usage limits
   - Monitor rate limiting

4. **Rumble Upload Failures**
   - Verify credentials are correct
   - Check Chrome/Chromium installation
   - Review Selenium WebDriver logs

5. **Logo Overlay Issues**
   - Verify logo file path in config.py
   - Check logo file format (PNG recommended)
   - Ensure logo file exists and is readable
   - Test logo positioning with single video test

6. **Permission Errors**
   - Run with appropriate file permissions
   - Check directory write access
   - Verify credential file permissions

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Important Legal & Ethical Guidelines

**Content Rights & Attribution:**
- Only process content you have rights to use
- Always check and respect Creative Commons license requirements
- Provide proper attribution when required by CC licenses
- Never process copyrighted content without permission

**Platform Compliance:**
- Follow YouTube and Rumble terms of service
- Respect platform community guidelines
- Don't engage in spam or misleading content practices
- Monitor your content for policy violations

**Best Practices:**
- Review generated content before publishing
- Monitor API usage to avoid quota exhaustion
- Keep backups of important configuration files
- Regularly update dependencies for security

**Attribution Examples:**
```
# For CC-BY content, include in description:
"Original video by [Creator Name] licensed under CC BY 4.0"
"Source: [Original Video URL]"

# For CC-BY-SA content:
"Derivative work based on [Original Title] by [Creator] (CC BY-SA 4.0)"
"This work is also licensed under CC BY-SA 4.0"
```

## 📧 Support

For questions, issues, or feature requests, please open an issue on GitHub or contact the maintainer.

---

**Built with ❤️ for content creators who value automation, quality, and legal compliance.**