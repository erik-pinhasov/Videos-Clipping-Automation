"""
AI-powered metadata generation optimized for viral content using OpenAI.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import openai
import config
from src.core.logger import get_logger
from src.core.exceptions import MetadataError, OpenAIError, QuotaExceededError


class MetadataService:
    """Generates viral-optimized metadata using OpenAI API."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Initialize OpenAI
        self.client = openai.OpenAI(api_key=self.config.OPENAI_API_KEY)
        
        # API usage tracking
        self.usage_file = "openai_usage.json"
        self.daily_usage = self._load_daily_usage()
        
        # Viral content strategies per channel
        self.channel_strategies = {
            'naturesmomentstv': {
                'focus': 'breathtaking nature moments',
                'emotions': ['wonder', 'peace', 'amazement'],
                'keywords': ['stunning', 'incredible', 'breathtaking', 'amazing', 'wild']
            },
            'navwildanimaldocumentary': {
                'focus': 'wildlife behavior and animal interactions',
                'emotions': ['excitement', 'curiosity', 'fascination'],
                'keywords': ['epic', 'wild', 'incredible', 'rare', 'amazing']
            },
            'wildnatureus2024': {
                'focus': 'pristine nature and scenic landscapes',
                'emotions': ['tranquility', 'awe', 'serenity'],
                'keywords': ['pristine', 'untouched', 'serene', 'beautiful', 'peaceful']
            },
            'ScenicScenes': {
                'focus': 'relaxing and healing natural environments',
                'emotions': ['calm', 'healing', 'relaxation'],
                'keywords': ['relaxing', 'healing', 'peaceful', 'calming', 'therapeutic']
            }
        }
    
    def generate(self, video_path: str, channel: str, original_title: str = None) -> Dict[str, Any]:
        """Generate viral-optimized metadata for video content."""
        try:
            self.logger.info("Generating AI metadata...")
            
            # Check daily usage limits
            if self._check_usage_limits():
                raise QuotaExceededError("Daily OpenAI usage limit reached")
            
            # Get channel strategy
            strategy = self.channel_strategies.get(channel, self.channel_strategies['naturesmomentstv'])
            
            # Generate metadata using OpenAI
            metadata = self._generate_with_openai(original_title, strategy, channel)
            
            # Track usage
            self._track_usage()
            
            self.logger.info(f"✓ AI metadata generated (API calls today: {self.daily_usage['count']})")
            self.logger.debug(f"Generated title: {metadata.get('title', 'N/A')}")
            
            return metadata
            
        except QuotaExceededError:
            self.logger.warning("OpenAI quota exceeded, using fallback metadata")
            return self.config.get_fallback_metadata(channel, original_title)
        except Exception as e:
            self.logger.warning(f"AI metadata generation failed: {e}, using fallback")
            return self.config.get_fallback_metadata(channel, original_title)
    
    def _generate_with_openai(self, original_title: str, strategy: Dict[str, Any], channel: str) -> Dict[str, Any]:
        """Generate metadata using OpenAI GPT."""
        try:
            # Build viral-focused prompt
            prompt = self._build_viral_prompt(original_title, strategy, channel)
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Cost-effective for metadata
                messages=[
                    {
                        "role": "system",
                        "content": "You are a viral content specialist who creates engaging YouTube titles, descriptions, and tags that maximize views and engagement. Remove all technical specifications like '4K', '60fps', 'HD', 'Ultra HD' from titles. Focus on emotional hooks and curiosity gaps."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.8,  # Creative but not too random
                top_p=0.9
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            metadata = self._parse_openai_response(content, strategy)
            
            return metadata
            
        except Exception as e:
            raise OpenAIError(f"OpenAI API call failed: {e}")
    
    def _build_viral_prompt(self, original_title: str, strategy: Dict[str, Any], channel: str) -> str:
        """Build a prompt optimized for viral content generation."""
        
        focus = strategy['focus']
        emotions = ', '.join(strategy['emotions'])
        keywords = ', '.join(strategy['keywords'])
        
        prompt = f"""
Create viral YouTube content metadata for a {focus} video.

Original title: "{original_title or 'Nature/Wildlife Content'}"
Channel focus: {focus}
Target emotions: {emotions}
Power keywords to use: {keywords}

Requirements:
1. TITLE: Create a compelling 60-80 character title that:
   - Removes ALL technical specs (4K, HD, 60fps, Ultra, etc.)
   - Uses emotional hooks and curiosity gaps
   - Includes power keywords: {keywords}
   - Evokes {emotions}
   - Is optimized for YouTube algorithm

2. DESCRIPTION: Write a 150-200 word description that:
   - Opens with an emotional hook
   - Uses strategic emojis (not excessive)
   - Includes call-to-action for engagement
   - Has relevant hashtags
   - Optimized for search and discovery

3. TAGS: Provide 12-15 tags that are:
   - Mix of broad and specific terms
   - Include trending keywords
   - Relevant to {focus}
   - Good for YouTube SEO

Format your response as JSON:
{{
    "title": "viral title here",
    "description": "engaging description here",
    "tags": ["tag1", "tag2", "tag3", ...]
}}
"""
        return prompt
    
    def _parse_openai_response(self, content: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenAI response into structured metadata."""
        try:
            # Try to parse as JSON first
            if content.strip().startswith('{'):
                metadata = json.loads(content)
                return self._validate_metadata(metadata, strategy)
            
            # Fallback parsing for non-JSON responses
            lines = content.strip().split('\n')
            metadata = {'title': '', 'description': '', 'tags': []}
            
            current_section = None
            for line in lines:
                line = line.strip()
                if 'title' in line.lower():
                    current_section = 'title'
                elif 'description' in line.lower():
                    current_section = 'description'
                elif 'tags' in line.lower():
                    current_section = 'tags'
                elif line and current_section:
                    if current_section == 'title':
                        metadata['title'] = line.strip('"').strip()
                    elif current_section == 'description':
                        metadata['description'] += line + ' '
                    elif current_section == 'tags':
                        # Parse tags from various formats
                        if ',' in line:
                            tags = [tag.strip().strip('"') for tag in line.split(',')]
                            metadata['tags'].extend(tags)
            
            return self._validate_metadata(metadata, strategy)
            
        except Exception as e:
            self.logger.warning(f"Could not parse OpenAI response: {e}")
            # Return fallback
            return {
                'title': 'Amazing Nature Moments You Need To See',
                'description': '🌿 Incredible moments from nature captured in stunning detail! 🦅✨\n\n👍 Like if you enjoyed this video\n🔔 Subscribe for more content\n💬 Comment your thoughts below\n\n#nature #amazing #viral #shorts',
                'tags': strategy.get('keywords', ['nature', 'wildlife', 'amazing'])
            }
    
    def _validate_metadata(self, metadata: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enhance generated metadata."""
        
        # Validate title
        title = metadata.get('title', '').strip()
        if not title or len(title) < 20:
            title = f"Amazing {strategy['focus'].title()} You Must See!"
        
        # Remove technical specs from title
        tech_terms = ['4K', '4k', 'HD', 'hd', 'Ultra HD', 'UHD', '60fps', '60 fps', 'High Definition']
        for term in tech_terms:
            title = title.replace(term, '').strip()
        
        # Clean up extra spaces
        title = ' '.join(title.split())
        
        # Limit title length
        if len(title) > 100:
            title = title[:97] + '...'
        
        # Validate description
        description = metadata.get('description', '').strip()
        if not description or len(description) < 50:
            keywords = ', '.join(strategy.get('keywords', ['amazing'])[:3])
            description = f"🌿 Incredible {strategy['focus']} captured in stunning detail! 🦅✨\n\n👍 Like if you enjoyed this video\n🔔 Subscribe for more content\n💬 Comment your thoughts below\n\n#{keywords.replace(', ', ' #')}"
        
        # Validate tags
        tags = metadata.get('tags', [])
        if not tags or len(tags) < 5:
            tags = strategy.get('keywords', []) + ['nature', 'wildlife', 'amazing', 'viral', 'shorts']
        
        # Limit tags and clean them
        tags = [tag.strip().lower().replace('#', '') for tag in tags if tag.strip()]
        tags = tags[:15]  # YouTube limit
        
        return {
            'title': title,
            'description': description,
            'tags': tags,
            'category_id': '15',  # Pets & Animals
            'privacy_status': 'public'
        }
    
    def _load_daily_usage(self) -> Dict[str, Any]:
        """Load daily API usage tracking."""
        try:
            if Path(self.usage_file).exists():
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                
                today = datetime.now().strftime('%Y-%m-%d')
                if data.get('date') == today:
                    return data
            
            # Return fresh daily usage
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'count': 0,
                'cost': 0.0
            }
            
        except Exception:
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'count': 0,
                'cost': 0.0
            }
    
    def _check_usage_limits(self) -> bool:
        """Check if daily usage limits are exceeded."""
        daily_limit = getattr(self.config, 'OPENAI_DAILY_LIMIT', 100)
        return self.daily_usage['count'] >= daily_limit
    
    def _track_usage(self) -> None:
        """Track API usage for cost monitoring."""
        try:
            self.daily_usage['count'] += 1
            self.daily_usage['cost'] += 0.002  # Approximate cost per call
            
            with open(self.usage_file, 'w') as f:
                json.dump(self.daily_usage, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Could not track usage: {e}")
    
    def enhance_subtitles(self, raw_transcript: str, channel: str) -> str:
        """Enhance raw transcript for engaging subtitles (OpenAI task)."""
        try:
            if self._check_usage_limits():
                return raw_transcript  # Return original if quota exceeded
            
            strategy = self.channel_strategies.get(channel, self.channel_strategies['naturesmomentstv'])
            
            prompt = f"""
Transform this raw transcript into engaging, viral-style subtitle text:

Raw transcript: "{raw_transcript}"

Requirements:
- Keep the core message intact
- Add emotional emphasis where appropriate
- Use engaging language that matches {strategy['focus']}
- Keep it natural and readable
- Don't add content that wasn't spoken
- Maximum 200 characters

Enhanced transcript:
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You enhance speech transcripts to be more engaging while keeping them accurate and natural."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            enhanced_text = response.choices[0].message.content.strip()
            self._track_usage()
            
            return enhanced_text
            
        except Exception as e:
            self.logger.warning(f"Subtitle enhancement failed: {e}")
            return raw_transcript