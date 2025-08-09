"""
Metadata generation service using AI for creating engaging video titles and descriptions.
"""

import openai
import random
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.core.logger import get_logger
from src.core.exceptions import MetadataError
import config


class MetadataService:
    """Generates metadata for videos using AI and fallback templates."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # Set up OpenAI client
        if self.config.OPENAI_API_KEY:
            openai.api_key = self.config.OPENAI_API_KEY
        
        self._api_calls_today = 0
    
    def generate(self, video_path: str, channel: str = None, original_title: str = None) -> Dict[str, Any]:
        """
        Generate metadata for a video.
        
        Args:
            video_path: Path to video file
            channel: Channel name for context
            original_title: Original video title for reference
            
        Returns:
            Dict containing title, description, and tags
        """
        try:
            # Check if we should use AI
            if not self.config.USE_AI_METADATA or not self.config.OPENAI_API_KEY:
                return self._generate_fallback_metadata(channel, original_title)
            
            # Check quota
            if self._api_calls_today >= self.config.OPENAI_API_DAILY_QUOTA:
                self.logger.warning("OpenAI API quota exceeded, using fallback metadata")
                return self._generate_fallback_metadata(channel, original_title)
            
            # Get channel context
            category = self.config.get_channel_category(channel) if channel else "content"
            channel_tags = self.config.get_channel_tags(channel) if channel else self.config.DEFAULT_TAGS
            
            # Generate AI metadata
            self.logger.info("Generating AI metadata...")
            ai_metadata = self._generate_ai_metadata(category, channel_tags, original_title)
            
            if ai_metadata:
                self._api_calls_today += 1
                self.logger.info(f"✓ AI metadata generated (API calls today: {self._api_calls_today})")
                return ai_metadata
            else:
                self.logger.warning("AI metadata generation failed, using fallback")
                return self._generate_fallback_metadata(channel, original_title)
                
        except Exception as e:
            self.logger.error(f"Metadata generation error: {e}")
            return self._generate_fallback_metadata(channel, original_title)
    
    def _generate_ai_metadata(self, category: str, tags: List[str], original_title: str = None) -> Optional[Dict[str, Any]]:
        """Generate metadata using OpenAI API."""
        try:
            # Create context-aware prompt
            prompt = self._create_metadata_prompt(category, tags, original_title)
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a expert content creator specializing in engaging video metadata for social media platforms."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            return self._parse_ai_response(content, tags)
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return None
    
    def _create_metadata_prompt(self, category: str, tags: List[str], original_title: str = None) -> str:
        """Create a context-aware prompt for metadata generation."""
        base_prompt = f"""
Create engaging YouTube Shorts metadata for a {category} video.

Context:
- Content type: {category}
- Target audience: People interested in {category} content
- Platform: YouTube Shorts (short-form vertical video)
- Available tags: {', '.join(tags[:10])}
"""
        
        if original_title:
            base_prompt += f"\n- Original title reference: {original_title}"
        
        base_prompt += f"""

Please provide:
1. A catchy title (max {self.config.MAX_TITLE_LENGTH} characters) that's optimized for YouTube Shorts
2. An engaging description (max {self.config.MAX_DESCRIPTION_LENGTH} characters) with relevant hashtags
3. 5-8 relevant tags from the provided list

Format your response as:
TITLE: [your title here]
DESCRIPTION: [your description here]
TAGS: [tag1, tag2, tag3, ...]
"""
        
        return base_prompt
    
    def _parse_ai_response(self, response: str, available_tags: List[str]) -> Dict[str, Any]:
        """Parse AI response into structured metadata."""
        try:
            lines = response.strip().split('\n')
            metadata = {
                "title": "",
                "description": "",
                "tags": []
            }
            
            for line in lines:
                line = line.strip()
                if line.startswith('TITLE:'):
                    metadata["title"] = line[6:].strip()
                elif line.startswith('DESCRIPTION:'):
                    metadata["description"] = line[12:].strip()
                elif line.startswith('TAGS:'):
                    tags_str = line[5:].strip()
                    # Parse tags and validate against available tags
                    parsed_tags = [tag.strip().lower() for tag in tags_str.split(',')]
                    metadata["tags"] = [tag for tag in parsed_tags if tag in [t.lower() for t in available_tags]]
            
            # Validate and clean up
            if not metadata["title"]:
                raise ValueError("No title generated")
            
            if not metadata["description"]:
                raise ValueError("No description generated")
            
            if not metadata["tags"]:
                metadata["tags"] = available_tags[:5]  # Use default tags
            
            # Truncate if needed
            metadata["title"] = metadata["title"][:self.config.MAX_TITLE_LENGTH]
            metadata["description"] = metadata["description"][:self.config.MAX_DESCRIPTION_LENGTH]
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Failed to parse AI response: {e}")
            return None
    
    def _generate_fallback_metadata(self, channel: str = None, original_title: str = None) -> Dict[str, Any]:
        """Generate fallback metadata when AI is not available."""
        return self.config.get_fallback_metadata(channel, original_title)
    
    def reset_daily_quota(self) -> None:
        """Reset daily API call counter."""
        self._api_calls_today = 0
        self.logger.info("Daily API quota counter reset")