import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# YouTube API imports
try:
    import google.auth.transport.requests
    import google.oauth2.credentials
    import googleapiclient.discovery
    import googleapiclient.errors
    from google_auth_oauthlib.flow import InstalledAppFlow
    YOUTUBE_AVAILABLE = True
except ImportError:
    YOUTUBE_AVAILABLE = False

import config
from src.core.logger import get_logger
from src.core.exceptions import UploadError, YouTubeUploadError, RumbleUploadError


class VideoUploader:
    """Handles uploads to YouTube and Rumble platforms."""
    
    def __init__(self, cfg: config.Config):
        self.config = cfg
        self.logger = get_logger(__name__)
        
        # YouTube setup
        self.youtube_service = None
        self.youtube_initialized = False
        
        # Rumble setup
        self.rumble_session = None
        self.rumble_initialized = False
        
        # Upload tracking
        self.upload_log_file = "upload_log.json"
        self.upload_history = self._load_upload_history()
        
        # Rate limiting
        self.last_youtube_upload = 0
        self.last_rumble_upload = 0
        # Minimum seconds between uploads; configurable
        self.min_upload_interval = int(getattr(self.config, 'YOUTUBE_MIN_UPLOAD_INTERVAL', 10))
        # YouTube retry config
        self.youtube_max_retries = int(getattr(self.config, 'YOUTUBE_UPLOAD_MAX_RETRIES', 3))
        self.youtube_retry_backoff_base = float(getattr(self.config, 'YOUTUBE_UPLOAD_RETRY_BACKOFF_BASE', 2.0))
        
        # Background task tracking (Rumble)
        self._rumble_tasks = {}
        self._rumble_task_counter = 0
        self._rumble_tasks_lock = threading.Lock()
        # Quota tracking
        self.youtube_quota_exceeded = False
    
    def initialize(self) -> bool:
        """Initialize upload services."""
        try:
            self.logger.info("Initializing upload services...")
            
            # Initialize YouTube
            youtube_success = self._initialize_youtube()
            if youtube_success:
                self.logger.info("✓ YouTube service initialized")
            else:
                self.logger.warning("⚠ YouTube initialization failed")
            
            # Initialize Rumble
            rumble_success = self._initialize_rumble()
            if rumble_success:
                self.logger.info("✓ Rumble service initialized")
            else:
                self.logger.warning("⚠ Rumble initialization failed")
            
            # At least one service should work
            overall_success = youtube_success or rumble_success
            
            if overall_success:
                self.logger.info("✓ Upload services ready")
            else:
                self.logger.error("✗ No upload services available")
            
            return overall_success
            
        except Exception as e:
            self.logger.error(f"Upload service initialization failed: {e}")
            return False
    
    def _initialize_youtube(self) -> bool:
        """Initialize YouTube Data API v3."""
        try:
            if not YOUTUBE_AVAILABLE:
                self.logger.warning("YouTube API libraries not available")
                return False
            
            # Check for credentials
            if not hasattr(self.config, 'YOUTUBE_CLIENT_SECRET_FILE'):
                self.logger.warning("YouTube client secret file not configured")
                return False
            
            client_secret_file = self.config.YOUTUBE_CLIENT_SECRET_FILE
            if not Path(client_secret_file).exists():
                self.logger.warning(f"YouTube client secret file not found: {client_secret_file}")
                return False
            
            # OAuth 2.0 scopes
            scopes = ['https://www.googleapis.com/auth/youtube.upload']
            
            # Token file for storing credentials
            token_file = 'credentials/youtube_token.json'
            Path('credentials').mkdir(exist_ok=True)
            
            credentials = None
            
            # Load existing credentials
            if Path(token_file).exists():
                try:
                    credentials = google.oauth2.credentials.Credentials.from_authorized_user_file(token_file, scopes)
                except Exception as e:
                    self.logger.debug(f"Could not load existing credentials: {e}")
            
            # Refresh or create new credentials
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    try:
                        credentials.refresh(google.auth.transport.requests.Request())
                    except Exception as e:
                        self.logger.debug(f"Token refresh failed: {e}")
                        credentials = None
                
                if not credentials:
                    # Run OAuth flow
                    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
                    credentials = flow.run_local_server(port=0)
                
                # Save credentials
                with open(token_file, 'w') as f:
                    f.write(credentials.to_json())
            
            # Build YouTube service
            self.youtube_service = googleapiclient.discovery.build('youtube', 'v3', credentials=credentials)
            self.youtube_initialized = True
            
            return True
            
        except Exception as e:
            self.logger.error(f"YouTube initialization failed: {e}")
            return False
    
    def _initialize_rumble(self) -> bool:
        """Initialize Rumble upload session."""
        try:
            # Check for Rumble credentials
            if not all(hasattr(self.config, attr) for attr in ['RUMBLE_USERNAME', 'RUMBLE_PASSWORD']):
                self.logger.warning("Rumble credentials not configured")
                return False
            
            # Create session with retry strategy
            self.rumble_session = requests.Session()
            
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.rumble_session.mount("http://", adapter)
            self.rumble_session.mount("https://", adapter)
            
            # Set headers
            self.rumble_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            self.rumble_initialized = True
            return True
            
        except Exception as e:
            self.logger.error(f"Rumble initialization failed: {e}")
            return False
    
    def upload_to_youtube(self, video_path: str, metadata: Dict[str, Any]) -> bool:
        """Upload video to YouTube."""
        try:
            if not self.youtube_initialized or not self.youtube_service:
                raise YouTubeUploadError("YouTube service not initialized")
            if self.youtube_quota_exceeded:
                self.logger.warning("Skipping YouTube upload: quota already exceeded this session.")
                return False

            attempts = max(1, self.youtube_max_retries)
            for attempt in range(1, attempts + 1):
                try:
                    self.logger.info(f"Starting YouTube upload (attempt {attempt}/{attempts}): {Path(video_path).name}")

                    # Rate limiting
                    self._enforce_rate_limiting('youtube')

                    # Prepare upload metadata
                    youtube_metadata = self._prepare_youtube_metadata(metadata, video_path)

                    # Upload video
                    upload_result = self._execute_youtube_upload(video_path, youtube_metadata)

                    if upload_result:
                        video_id = upload_result.get('id')
                        video_url = f"https://youtube.com/watch?v={video_id}"

                        # Log successful upload
                        self._log_upload('youtube', video_path, video_url, metadata)

                        # Optional delete clip after successful upload
                        try:
                            if getattr(self.config, 'DELETE_CLIP_AFTER_UPLOAD', True):
                                p = Path(video_path)
                                if p.exists():
                                    p.unlink()
                                    self.logger.info(f"Deleted uploaded clip: {p.name}")
                        except Exception as del_err:
                            self.logger.debug(f"Could not delete clip after upload: {del_err}")

                        self.logger.info(f"✓ YouTube upload successful: {video_url}")
                        return True
                    else:
                        raise YouTubeUploadError("Upload returned no result")

                except Exception as e:
                    # Log and retry if attempts remain
                    msg = str(e)
                    # Stop immediately on quota exceeded
                    if ('quota' in msg.lower()) or ('quotaExceeded' in msg) or ('403' in msg and 'quota' in msg.lower()):
                        self.youtube_quota_exceeded = True
                        self.logger.error(f"YouTube quota exceeded. Aborting further uploads this session.")
                        return False
                    if attempt < attempts:
                        wait_s = min(60.0, (self.youtube_retry_backoff_base ** (attempt - 1)) * 5.0)
                        self.logger.warning(f"YouTube upload attempt {attempt} failed: {e}. Retrying in {wait_s:.1f}s...")
                        time.sleep(wait_s)
                    else:
                        raise

        except Exception as e:
            self.logger.error(f"YouTube upload failed: {e}")
            return False

    def upload_to_rumble(self, video_path: str, title: str, description: str, tags: List[str]) -> bool:
        """Upload video to Rumble synchronously and return the resulting URL if detected."""
        if not self.rumble_initialized or not self.rumble_session:
            raise RumbleUploadError("Rumble service not initialized")

        self.logger.info(f"Starting Rumble upload: {Path(video_path).name}")
        self._enforce_rate_limiting('rumble')
        
        try:
            self.logger.info("Using Playwright for Rumble upload")
            upload_result = self._upload_to_rumble_via_playwright(video_path, title, description, tags)
        except Exception as e:
            self.logger.warning(f"Playwright path failed: {e}. Falling back to requests flow.")
            upload_result = False

        self.logger.info(f"Rumble upload completed with URL: {upload_result}")
        return upload_result

    def start_rumble_upload_background(self, video_path: str, title: str, description: str, tags: List[str]) -> str:
        """Start Rumble upload in a background thread and return a task id."""
        with self._rumble_tasks_lock:
            self._rumble_task_counter += 1
            task_id = f"rumble-{self._rumble_task_counter}"
            self._rumble_tasks[task_id] = {
                'id': task_id,
                'status': 'running',
                'video': Path(video_path).name,
                'result_url': None,
                'error': None,
                'started_at': datetime.now().isoformat(),
                'finished_at': None,
            }

        def _worker():
            try:
                url = self.upload_rumble_and_get_url(video_path, title, description, tags)
                with self._rumble_tasks_lock:
                    self._rumble_tasks[task_id]['status'] = 'success' if url else 'failed'
                    self._rumble_tasks[task_id]['result_url'] = url
                    self._rumble_tasks[task_id]['finished_at'] = datetime.now().isoformat()
            except Exception as e:
                with self._rumble_tasks_lock:
                    self._rumble_tasks[task_id]['status'] = 'failed'
                    self._rumble_tasks[task_id]['error'] = str(e)
                    self._rumble_tasks[task_id]['finished_at'] = datetime.now().isoformat()

        t = threading.Thread(target=_worker, name=f"RumbleUpload-{task_id}", daemon=True)
        t.start()
        self.logger.info(f"Started background Rumble upload task: {task_id}")
        return task_id

    def get_rumble_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a background Rumble upload task."""
        with self._rumble_tasks_lock:
            return dict(self._rumble_tasks.get(task_id)) if task_id in self._rumble_tasks else None

    def _upload_to_rumble_via_playwright(self, video_path: str, title: str, description: str, tags: List[str]) -> bool:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.warning("Playwright is not installed. Run: pip install playwright && playwright install chromium")
            return False

        rumble_user = getattr(self.config, 'RUMBLE_USERNAME', None)
        rumble_pass = getattr(self.config, 'RUMBLE_PASSWORD', None)
        
        if not rumble_user or not rumble_pass:
            self.logger.error("Rumble credentials missing in config")
            return False

        headless = bool(getattr(self.config, 'PLAYWRIGHT_HEADLESS', True))
        slow_mo = int(getattr(self.config, 'PLAYWRIGHT_SLOWMO_MS', 0))
        
        with sync_playwright() as p:
            # Launch browser
            try:
                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
            except Exception as e:
                self.logger.error(f"Failed to launch browser: {e}")
                return False
                
            context = browser.new_context()
            page = context.new_page()

            try:
                # Step 1: Login
                self.logger.info("Logging in to Rumble...")
                page.goto("https://rumble.com/login.php", wait_until='load')
                page.fill('input[name="username"]', rumble_user)
                page.fill('input[name="password"]', rumble_pass)
                time.sleep(1)
                page.click('button[type="submit"]')

                page.goto("https://rumble.com/upload.php", wait_until='load')
                page.set_input_files('#Filedata', video_path)
                time.sleep(1)
                
                page.fill('input[name="title"]', title[:100])
                page.fill('textarea[name="description"]', description[:2000])
                page.fill('input[name="tags"]', ','.join(tags[:10]))
                
                cat_input = page.locator('input[name="primary-category"]').first
                if cat_input.is_visible():
                    cat_input.click()
                    cat_input.fill('Entertainment')
                    page.keyboard.press('Enter')
                        
                cat_input = page.locator('input[name="secondary-category"]').first
                if cat_input.is_visible():
                    cat_input.click()
                    cat_input.fill('Wild Wildlife')
                    page.keyboard.press('Enter')

                # Wait for video upload to complete (100%)
                self.logger.info("Waiting for video upload to complete...")
                upload_complete = False
                for _ in range(720):  # Wait up to 60 minutes for upload
                    try:
                        percent_element = page.locator('h2.num_percent')
                        if percent_element.is_visible():
                            percent_text = percent_element.text_content()
                            if percent_text and "100%" in percent_text:
                                self.logger.info("Video upload completed (100%)")
                                upload_complete = True
                                break
                                
                    except Exception as e:
                        self.logger.debug(f"Upload progress check error: {e}")
                        pass
                    
                    time.sleep(5)
                
                time.sleep(1)
                self.logger.info("Selecting thumbnail...")
                try:
                    thumbs = page.locator('div.thumbContainers a')
                    if thumbs.count() > 0:
                        thumbs.first.click()
                    else:
                        self.logger.warning("No thumbnails found")
                except Exception as e:
                    self.logger.warning(f"Could not select thumbnail: {e}")
                                
                time.sleep(1)
                page.click('#submitForm')
                page.wait_for_load_state('load', timeout=120000)
                page.wait_for_selector('a[crcval="6"]', timeout=60000)
                page.click('a[crcval="6"]')
                time.sleep(1)

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                page.wait_for_selector('label[for="crights"]', timeout=30000)
                page.click('label[for="crights"]')
                
                page.wait_for_selector('label[for="cterms"]', timeout=30000)
                page.click('label[for="cterms"]')
                
                time.sleep(1)
                page.click('#submitForm2')
                page.wait_for_load_state('load', timeout=120000)
                
                # Wait for upload completion confirmation
                upload_confirmed = False
                
                for _ in range(24):  # Wait up to 2 minutes
                    try:
                        # Check for success indicators - multiple possible texts
                        success_indicators = [
                            'text=/Video Upload Complete/i',
                            'text=/success/i', 
                            'text=/complete/i',
                            'text=/published/i',
                            'text=/uploaded/i',
                            'h3.title:has-text("Video Upload Complete")',
                            'text=/upload.*complete/i',
                            'text=/successfully.*uploaded/i'
                        ]
                        
                        for indicator in success_indicators:
                            success_element = page.locator(indicator).first
                            if success_element.is_visible():
                                success_text = success_element.text_content()
                                self.logger.info(f"✓ Upload completed! Found: '{success_text}'")
                                upload_confirmed = True
                                break
                        
                        if upload_confirmed:
                            break
                            
                    except Exception as e:
                        self.logger.debug(f"Success check error: {e}")
                    
                    time.sleep(5)
                
                return True
                
            except Exception as e:
                self.logger.error(f"Upload failed: {e}")
                return False
                
            finally:
                context.close()
                browser.close()

        return False
    
    def _prepare_youtube_metadata(self, metadata: Dict[str, Any], video_path: str) -> Dict[str, Any]:
        """Prepare metadata for YouTube upload."""
        # Adjust title for Shorts with safe defaults
        fallback_title = getattr(self.config, 'METADATA_FALLBACK_TITLE', 'Wildlife Highlight')
        base_title = metadata.get('title') or fallback_title
        title = str(base_title).strip()[:100] or 'Untitled Video'
        if getattr(self.config, 'YOUTUBE_FORCE_SHORTS_HASHTAG', True):
            if '#shorts' not in title.lower():
                title = f"{title} #shorts"

        # Kids setting
        made_for_kids = getattr(self.config, 'YOUTUBE_MADE_FOR_KIDS', False)

        # Normalize fields
        description = (metadata.get('description') or '').strip()
        tags_raw = metadata.get('tags') or []
        if isinstance(tags_raw, str):
            tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
        else:
            tags = [str(t).strip() for t in tags_raw if str(t).strip()]

        return {
            'snippet': {
                'title': title,
                'description': description[:5000],
                'tags': tags[:500],  # YouTube limit
                'categoryId': metadata.get('category_id', '15'),  # Pets & Animals
                'defaultLanguage': 'en',
                'defaultAudioLanguage': 'en'
            },
            'status': {
                'privacyStatus': metadata.get('privacy_status', 'public'),
                'embeddable': True,
                'license': 'youtube',
                'publicStatsViewable': True,
                'madeForKids': made_for_kids
            }
        }
    
    def _execute_youtube_upload(self, video_path: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute the actual YouTube upload."""
        try:
            # Create upload request
            import mimetypes
            mime = mimetypes.guess_type(video_path)[0] or 'application/octet-stream'
            media_body = googleapiclient.http.MediaFileUpload(
                video_path,
                chunksize=-1,  # Upload in single chunk
                resumable=True,
                mimetype=mime
            )
            
            insert_request = self.youtube_service.videos().insert(
                part=','.join(metadata.keys()),
                body=metadata,
                media_body=media_body
            )
            
            # Execute upload with progress tracking
            response = None
            start_time = time.time()
            
            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    
                    if status:
                        progress = int(status.progress() * 100)
                        elapsed = time.time() - start_time
                        self.logger.info(f"  Upload progress: {progress}% ({elapsed:.1f}s)")
                        
                except googleapiclient.errors.HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        # Recoverable errors
                        self.logger.warning(f"Recoverable error: {e}")
                        time.sleep(5)
                        continue
                    else:
                        raise YouTubeUploadError(f"YouTube API error: {e}")
            
            self.last_youtube_upload = time.time()
            return response
            
        except Exception as e:
            raise YouTubeUploadError(f"YouTube upload execution failed: {e}")
    
    def _enforce_rate_limiting(self, platform: str) -> None:
        """Enforce rate limiting between uploads."""
        try:
            if platform == 'youtube':
                last_upload = self.last_youtube_upload
            else:  # rumble
                last_upload = self.last_rumble_upload
            
            if last_upload > 0:
                elapsed = time.time() - last_upload
                if elapsed < self.min_upload_interval:
                    sleep_time = self.min_upload_interval - elapsed
                    self.logger.info(f"Rate limiting: waiting {sleep_time:.1f}s before {platform} upload")
                    time.sleep(sleep_time)
                    
        except Exception as e:
            self.logger.debug(f"Rate limiting error: {e}")
    
    def _load_upload_history(self) -> Dict[str, Any]:
        """Load upload history for tracking."""
        try:
            if Path(self.upload_log_file).exists():
                with open(self.upload_log_file, 'r') as f:
                    return json.load(f)
            return {'uploads': [], 'stats': {'youtube': 0, 'rumble': 0}}
        except:
            return {'uploads': [], 'stats': {'youtube': 0, 'rumble': 0}}
    
    def _log_upload(self, platform: str, video_path: str, result_url: str, metadata: Dict[str, Any]) -> None:
        """Log successful upload."""
        try:
            upload_entry = {
                'timestamp': datetime.now().isoformat(),
                'platform': platform,
                'video_file': Path(video_path).name,
                'title': metadata.get('title', 'Unknown'),
                'result_url': result_url,
                'file_size_mb': Path(video_path).stat().st_size / (1024 * 1024)
            }
            
            self.upload_history['uploads'].append(upload_entry)
            self.upload_history['stats'][platform] = self.upload_history['stats'].get(platform, 0) + 1
            
            # Keep only last 100 uploads to prevent file from growing too large
            if len(self.upload_history['uploads']) > 100:
                self.upload_history['uploads'] = self.upload_history['uploads'][-100:]
            
            # Save to file
            with open(self.upload_log_file, 'w') as f:
                json.dump(self.upload_history, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Could not log upload: {e}")
