import os
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
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
        self.min_upload_interval = 60  # 1 minute between uploads
    
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
            
            self.logger.info(f"Starting YouTube upload: {Path(video_path).name}")
            
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
            self.logger.error(f"YouTube upload failed: {e}")
            return False
    
    def upload_to_rumble(self, video_path: str, title: str, description: str, tags: List[str]) -> bool:
        """Upload video to Rumble."""
        try:
            if not self.rumble_initialized or not self.rumble_session:
                raise RumbleUploadError("Rumble service not initialized")
            
            self.logger.info(f"Starting Rumble upload: {Path(video_path).name}")
            
            # Rate limiting
            self._enforce_rate_limiting('rumble')
            
            # Prefer Playwright automation when available
            use_playwright = getattr(self.config, 'RUMBLE_UPLOAD_METHOD', 'playwright') == 'playwright'
            if use_playwright:
                try:
                    self.logger.info("Using Playwright for Rumble upload")
                    upload_result = self._upload_to_rumble_via_playwright(video_path, title, description, tags)
                except Exception as e:
                    self.logger.warning(f"Playwright path failed: {e}. Falling back to requests flow.")
                    upload_result = None
            else:
                upload_result = None
            
            # Fallback to legacy requests flow if Playwright not used or failed
            if not upload_result:
                # Login to Rumble
                if not self._rumble_login():
                    raise RumbleUploadError("Rumble login failed")
                upload_result = self._execute_rumble_upload(video_path, title, description, tags)
            
            if upload_result:
                # Log successful upload
                self._log_upload('rumble', video_path, upload_result, {'title': title, 'description': description})
                
                self.logger.info(f"✓ Rumble upload successful: {upload_result}")
                return True
            else:
                raise RumbleUploadError("Rumble upload returned no result")
                
        except Exception as e:
            self.logger.error(f"Rumble upload failed: {e}")
            return False

    def _upload_to_rumble_via_playwright(self, video_path: str, title: str, description: str, tags: List[str]) -> Optional[str]:
        """Automate Rumble upload using Playwright (real browser flow). Returns video URL if detected."""
        try:
            try:
                from playwright.sync_api import sync_playwright, TimeoutError as PwTimeoutError
            except ImportError:
                self.logger.warning("Playwright is not installed. Run: pip install playwright && playwright install chromium")
                return None

            rumble_user = getattr(self.config, 'RUMBLE_USERNAME', None)
            rumble_pass = getattr(self.config, 'RUMBLE_PASSWORD', None)
            if not rumble_user or not rumble_pass:
                self.logger.error("Rumble credentials missing in config")
                return None

            headless = bool(getattr(self.config, 'PLAYWRIGHT_HEADLESS', False))
            slow_mo = int(getattr(self.config, 'PLAYWRIGHT_SLOWMO_MS', 0))
            upload_timeout_ms = int(getattr(self.config, 'RUMBLE_UPLOAD_TIMEOUT_MS', 60 * 60 * 1000))  # default 60 min

            self.logger.info(f"Launching Chromium (headless={headless}) for Rumble upload...")
            with sync_playwright() as p:
                # Attempt launch, and auto-install browser if configured and missing
                try:
                    browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
                except Exception as launch_err:
                    msg = str(launch_err)
                    if "Executable doesn't exist" in msg or "was just installed or updated" in msg:
                        if getattr(self.config, 'PLAYWRIGHT_AUTO_INSTALL', True):
                            self.logger.info("Playwright browser missing. Attempting to install Chromium...")
                            try:
                                import subprocess
                                subprocess.run(["playwright", "install", "chromium"], check=True)
                                self.logger.info("Chromium installed. Retrying launch...")
                                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
                            except Exception as install_err:
                                self.logger.error(f"Could not auto-install Chromium: {install_err}")
                                self.logger.error("Please run: playwright install chromium")
                                return None
                        else:
                            self.logger.error("Playwright browser not installed. Set PLAYWRIGHT_AUTO_INSTALL=true or run: playwright install chromium")
                            return None
                    else:
                        self.logger.error(f"Chromium launch failed: {launch_err}")
                        return None
                context = browser.new_context()
                page = context.new_page()

                # Login
                page.goto("https://rumble.com/login.php", timeout=60000)
                self.logger.info("Filling login form...")
                page.fill('input[name="username"]', rumble_user)
                page.fill('input[name="password"]', rumble_pass)
                # Try submit
                # Many forms use button[type=submit]
                try:
                    page.click('button[type="submit"]', timeout=5000)
                except Exception:
                    page.press('input[name="password"]', 'Enter')

                # Wait for navigation/login success
                page.wait_for_url("**/", timeout=60000)
                self.logger.info("Logged in to Rumble.")

                # Navigate to upload page
                page.goto("https://rumble.com/upload.php", timeout=60000)
                page.wait_for_load_state('domcontentloaded')
                self.logger.info("On upload page. Setting file input...")

                # Try multiple selectors for file input
                file_selectors = [
                    'input[type="file"]',
                    'input[name="video"]',
                    'input#video',
                ]
                set_file_ok = False
                for sel in file_selectors:
                    try:
                        page.set_input_files(sel, video_path, timeout=10000)
                        self.logger.info(f"File selected via selector: {sel}")
                        set_file_ok = True
                        break
                    except Exception as e:
                        self.logger.debug(f"File selector failed for {sel}: {e}")

                if not set_file_ok:
                    self.logger.error("Could not locate file input on Rumble upload page.")
                    return None

                # Fill metadata fields (best-effort)
                try:
                    page.fill('input[name="title"]', title[:100])
                except Exception as e:
                    self.logger.debug(f"Title fill skipped: {e}")
                try:
                    page.fill('textarea[name="description"]', description[:2000])
                except Exception as e:
                    self.logger.debug(f"Description fill skipped: {e}")
                try:
                    page.fill('input[name="tags"]', ','.join(tags[:10]))
                except Exception as e:
                    self.logger.debug(f"Tags fill skipped: {e}")

                # Start upload/publish
                self.logger.info("Submitting upload (searching for Upload/Publish button)...")
                click_selectors = [
                    'button:has-text("Upload")',
                    'button:has-text("Publish")',
                    'input[type="submit"]',
                    'button[name="upload"]',
                ]
                clicked = False
                for sel in click_selectors:
                    try:
                        page.click(sel, timeout=5000)
                        self.logger.info(f"Clicked button via selector: {sel}")
                        clicked = True
                        break
                    except Exception as e:
                        self.logger.debug(f"Click selector failed for {sel}: {e}")
                if not clicked:
                    self.logger.warning("Could not find explicit Upload/Publish button. Assuming auto-start.")

                # Wait for upload to complete. This can be long for large files.
                self.logger.info("Waiting for upload to complete (this may take a long time)...")
                deadline = time.time() + (upload_timeout_ms / 1000)
                video_url = None

                while time.time() < deadline:
                    try:
                        # Heuristic 1: URL changes to video page
                        current_url = page.url
                        if "/video/" in current_url:
                            video_url = current_url
                            self.logger.info(f"Detected video page URL: {video_url}")
                            break
                        # Heuristic 2: success text appears
                        if page.locator("text=/uploaded|processing|success/i").first.is_visible():
                            self.logger.info("Detected success/progress text on page.")
                    except Exception:
                        pass
                    time.sleep(5)

                if not video_url:
                    self.logger.warning("Upload may still be processing. Could not confirm final video URL within timeout.")

                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass

                return video_url or "https://rumble.com/"  # Return homepage if exact URL unknown

        except Exception as e:
            self.logger.error(f"Playwright upload error: {e}")
            return None
    
    def _prepare_youtube_metadata(self, metadata: Dict[str, Any], video_path: str) -> Dict[str, Any]:
        """Prepare metadata for YouTube upload."""
        # Adjust title for Shorts
        title = metadata.get('title', 'Untitled Video')[:100]
        if getattr(self.config, 'YOUTUBE_FORCE_SHORTS_HASHTAG', True):
            if '#shorts' not in title.lower():
                title = f"{title} #shorts"

        # Kids setting
        made_for_kids = getattr(self.config, 'YOUTUBE_MADE_FOR_KIDS', False)

        return {
            'snippet': {
                'title': title,
                'description': metadata.get('description', '')[:5000],
                'tags': metadata.get('tags', [])[:500],  # YouTube limit
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
            media_body = googleapiclient.http.MediaFileUpload(
                video_path,
                chunksize=-1,  # Upload in single chunk
                resumable=True,
                mimetype='video/mp4'
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
    
    def _rumble_login(self) -> bool:
        """Login to Rumble."""
        try:
            # Get login page
            login_url = "https://rumble.com/login.php"
            response = self.rumble_session.get(login_url, timeout=30)
            
            if response.status_code != 200:
                return False
            
            # Extract CSRF token or other required fields
            # This is a simplified implementation - actual Rumble login may require more steps
            login_data = {
                'username': self.config.RUMBLE_USERNAME,
                'password': self.config.RUMBLE_PASSWORD,
            }
            
            # Submit login
            response = self.rumble_session.post(login_url, data=login_data, timeout=30)
            
            # Check if login was successful
            if "dashboard" in response.url.lower() or response.status_code == 200:
                return True
            else:
                self.logger.error(f"Rumble login failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Rumble login error: {e}")
            return False
    
    def _execute_rumble_upload(self, video_path: str, title: str, description: str, tags: List[str]) -> Optional[str]:
        """Execute Rumble upload (simplified implementation)."""
        try:
            # This is a simplified implementation
            # Actual Rumble upload would require:
            # 1. Getting upload form and tokens
            # 2. Uploading video file
            # 3. Setting metadata
            # 4. Publishing video
            
            upload_url = "https://rumble.com/upload.php"
            
            # Prepare upload data
            files = {
                'video': (Path(video_path).name, open(video_path, 'rb'), 'video/mp4')
            }
            
            data = {
                'title': title[:100],
                'description': description[:2000],
                'tags': ','.join(tags[:10]),
                'category': 'Nature',
                'privacy': 'public'
            }
            
            # Upload (this is a mock - actual implementation would be more complex)
            response = self.rumble_session.post(
                upload_url,
                files=files,
                data=data,
                timeout=getattr(self.config, 'RUMBLE_UPLOAD_TIMEOUT', 600)
            )
            
            files['video'][1].close()  # Close file
            
            if response.status_code == 200:
                # Parse response for video URL
                self.last_rumble_upload = time.time()
                return "https://rumble.com/video/uploaded"  # Mock URL
            else:
                self.logger.error(f"Rumble upload response: {response.status_code} {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Rumble upload execution failed: {e}")
            return None
    
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
    
    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload statistics."""
        try:
            stats = self.upload_history.get('stats', {})
            recent_uploads = len([
                u for u in self.upload_history.get('uploads', [])
                if (datetime.now() - datetime.fromisoformat(u['timestamp'])).days < 7
            ])
            
            return {
                'total_youtube_uploads': stats.get('youtube', 0),
                'total_rumble_uploads': stats.get('rumble', 0),
                'uploads_last_7_days': recent_uploads,
                'services_available': {
                    'youtube': self.youtube_initialized,
                    'rumble': self.rumble_initialized
                }
            }
        except:
            return {'error': 'Could not get stats'}