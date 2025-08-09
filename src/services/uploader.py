"""
Video uploader service for YouTube and Rumble platforms.
"""

import os
import time
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from src.core.logger import get_logger
from src.core.exceptions import UploadError
import config

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class VideoUploader:
    """Handles video uploads to YouTube and Rumble."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        self.youtube_service = None
        self._upload_count_today = 0
        self._last_reset_time = time.time()
        
        # YouTube API scopes
        self.SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def initialize(self) -> bool:
        """Initialize upload services."""
        try:
            # Initialize YouTube service
            if GOOGLE_API_AVAILABLE:
                self.youtube_service = self._initialize_youtube()
                if self.youtube_service:
                    self.logger.info("✓ YouTube upload service initialized")
                else:
                    self.logger.warning("YouTube upload service initialization failed")
            else:
                self.logger.warning("Google API libraries not available for YouTube uploads")
            
            # Check Selenium for Rumble
            if not SELENIUM_AVAILABLE:
                self.logger.warning("Selenium not available for Rumble uploads")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize upload services: {e}")
            return False
    
    def _initialize_youtube(self) -> Optional[Any]:
        """Initialize YouTube API service."""
        try:
            creds = None
            token_file = getattr(self.config, 'YOUTUBE_TOKEN_FILE', 'credentials/youtube_token.json')
            secrets_file = getattr(self.config, 'YOUTUBE_CLIENT_SECRETS_FILE', 'credentials/client_secret.json')
            
            # Load existing token
            if os.path.exists(token_file):
                creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
            
            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(secrets_file):
                        self.logger.error(f"YouTube client secrets file not found: {secrets_file}")
                        return None
                    
                    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            return build('youtube', 'v3', credentials=creds)
            
        except Exception as e:
            self.logger.error(f"YouTube authentication failed: {e}")
            return None
    
    def upload_to_youtube(self, video_path: str, metadata: Dict[str, Any]) -> bool:
        """Upload video to YouTube."""
        try:
            if not self.youtube_service:
                raise UploadError("YouTube service not initialized")
            
            self._check_upload_limits()
            
            # Prepare upload metadata
            body = {
                'snippet': {
                    'title': metadata.get('title', 'Untitled Video'),
                    'description': metadata.get('description', ''),
                    'tags': metadata.get('tags', []),
                    'categoryId': metadata.get('category_id', '15')  # Pets & Animals
                },
                'status': {
                    'privacyStatus': metadata.get('privacy_status', 'public'),
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Create media upload
            media = MediaFileUpload(
                video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )
            
            self.logger.info(f"Starting YouTube upload: {Path(video_path).name}")
            
            # Execute upload
            insert_request = self.youtube_service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            video_id = self._execute_upload_request(insert_request)
            
            if video_id:
                self.logger.info(f"✓ YouTube upload successful: https://youtube.com/watch?v={video_id}")
                self._upload_count_today += 1
                return True
            else:
                raise UploadError("Upload completed but no video ID returned")
                
        except Exception as e:
            raise UploadError(f"YouTube upload failed: {e}")
    
    def _execute_upload_request(self, insert_request) -> Optional[str]:
        """Execute the upload request with retry logic."""
        response = None
        error = None
        retry = 0
        max_retries = 3
        
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if response is not None:
                    if 'id' in response:
                        return response['id']
                    else:
                        raise UploadError(f"Upload failed: {response}")
                        
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # Retriable error
                    error = f"Retriable HTTP error {e.resp.status}: {e.content}"
                    retry += 1
                    if retry > max_retries:
                        break
                    
                    wait_time = 2 ** retry
                    self.logger.warning(f"Retriable error, waiting {wait_time}s: {error}")
                    time.sleep(wait_time)
                else:
                    raise UploadError(f"HTTP error {e.resp.status}: {e.content}")
                    
            except Exception as e:
                raise UploadError(f"Upload error: {e}")
        
        if error:
            raise UploadError(f"Upload failed after {max_retries} retries: {error}")
        
        return None
    
    def upload_to_rumble(self, video_path: str, title: str, description: str, tags: List[str]) -> bool:
        """Upload video to Rumble using browser automation."""
        try:
            if not SELENIUM_AVAILABLE:
                self.logger.warning("Selenium not available, skipping Rumble upload")
                return False
            
            if not getattr(self.config, 'RUMBLE_USERNAME') or not getattr(self.config, 'RUMBLE_PASSWORD'):
                self.logger.warning("Rumble credentials not configured, skipping upload")
                return False
            
            self.logger.info(f"Starting Rumble upload: {Path(video_path).name}")
            
            # Setup Chrome options
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            
            driver = webdriver.Chrome(options=options)
            
            try:
                success = self._rumble_upload_process(driver, video_path, title, description, tags)
                
                if success:
                    self.logger.info("✓ Rumble upload successful")
                    return True
                else:
                    raise UploadError("Rumble upload process failed")
                    
            finally:
                driver.quit()
                
        except Exception as e:
            raise UploadError(f"Rumble upload failed: {e}")
    
    def _rumble_upload_process(self, driver, video_path: str, title: str, description: str, tags: List[str]) -> bool:
        """Execute Rumble upload process."""
        try:
            # Navigate to Rumble
            driver.get("https://rumble.com/upload.php")
            
            # Login
            driver.find_element(By.NAME, "username").send_keys(self.config.RUMBLE_USERNAME)
            driver.find_element(By.NAME, "password").send_keys(self.config.RUMBLE_PASSWORD)
            driver.find_element(By.XPATH, "//button[@type='submit']").click()
            
            # Wait for upload page
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
            )
            
            # Upload file
            file_input = driver.find_element(By.XPATH, "//input[@type='file']")
            file_input.send_keys(os.path.abspath(video_path))
            
            # Fill metadata
            title_field = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.NAME, "title"))
            )
            title_field.clear()
            title_field.send_keys(title)
            
            description_field = driver.find_element(By.NAME, "description")
            description_field.clear()
            description_field.send_keys(description)
            
            # Add tags
            if tags:
                tags_field = driver.find_element(By.NAME, "tags")
                tags_field.send_keys(", ".join(tags))
            
            # Submit upload
            submit_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Upload')]")
            submit_button.click()
            
            # Wait for upload completion
            WebDriverWait(driver, getattr(self.config, 'RUMBLE_UPLOAD_TIMEOUT', 600)).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Upload complete')]"))
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rumble upload process error: {e}")
            return False
    
    def _check_upload_limits(self) -> None:
        """Check daily upload limits."""
        current_time = time.time()
        
        # Reset daily counter
        if current_time - self._last_reset_time > 86400:  # 24 hours
            self._upload_count_today = 0
            self._last_reset_time = current_time
        
        # Check limits
        max_uploads = getattr(self.config, 'MAX_DAILY_UPLOADS', 50)
        if self._upload_count_today >= max_uploads:
            raise UploadError("Daily upload limit reached")
    
    def add_subtitles_to_youtube_video(self, video_id: str, subtitle_file: str) -> bool:
        """Add subtitles to uploaded YouTube video."""
        try:
            if not self.youtube_service or not os.path.exists(subtitle_file):
                return False
            
            media = MediaFileUpload(subtitle_file)
            
            insert_request = self.youtube_service.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": "en",
                        "name": "English"
                    }
                },
                media_body=media
            )
            
            insert_request.execute()
            self.logger.info(f"✓ Subtitles added to YouTube video: {video_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add subtitles: {e}")
            return False