import time
import json
import subprocess
import shutil
import threading
import config
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
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
            # Check and compress video if needed
            video_path = self._check_and_compress_video(video_path)
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
                # Check and compress video if needed  
                processed_video_path = self._check_and_compress_video(video_path)
                
                url = self.upload_to_rumble(processed_video_path, title, description, tags)
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
    
    def _get_file_size_gb(self, file_path: str) -> float:
        """Get file size in GB."""
        try:
            size_bytes = Path(file_path).stat().st_size
            size_gb = size_bytes / (1024 * 1024 * 1024)
            return size_gb
        except Exception as e:
            self.logger.error(f"Could not get file size for {file_path}: {e}")
            return 0
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video information using ffprobe."""
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                return {}
            
            duration = float(data.get('format', {}).get('duration', 0))
            bitrate = int(data.get('format', {}).get('bit_rate', 0))
            
            return {
                'duration': duration,
                'bitrate': bitrate,
                'width': video_stream.get('width', 0),
                'height': video_stream.get('height', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Could not get video info for {video_path}: {e}")
            return {}
    
    def _compress_video(self, input_path: str, output_path: str, target_size_gb: float = 14.0) -> bool:
        """Compress video to target size using ffmpeg."""
        try:
            self.logger.info(f"Compressing video: {Path(input_path).name}")
            
            # Get video info
            video_info = self._get_video_info(input_path)
            duration = video_info.get('duration', 0)
            
            if duration <= 0:
                self.logger.error("Could not determine video duration for compression")
                return False
            
            # Calculate target bitrate (in bits per second)
            # Target size in bytes = target_size_gb * 1024^3
            # Bitrate = (target_size_bytes * 8) / duration_seconds
            target_size_bytes = target_size_gb * 1024 * 1024 * 1024
            target_bitrate = int((target_size_bytes * 8) / duration)
            
            # Leave some room for audio and container overhead
            video_bitrate = int(target_bitrate * 0.9)  # 90% for video
            audio_bitrate = 128000  # 128k for audio
            
            self.logger.info(f"Target video bitrate: {video_bitrate // 1000}k")
            
            # FFmpeg compression command
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '28',
                '-maxrate', f'{video_bitrate}',
                '-bufsize', f'{video_bitrate * 2}',
                '-c:a', 'aac',
                '-b:a', f'{audio_bitrate}',
                '-movflags', '+faststart',
                '-y',  # Overwrite output file
                output_path
            ]
            
            # Run compression
            self.logger.info("Starting video compression (this may take a while)...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"FFmpeg compression failed: {result.stderr}")
                return False
            
            # Check if compression was successful
            if not Path(output_path).exists():
                self.logger.error("Compressed file was not created")
                return False
            
            # Log compression results
            original_size = self._get_file_size_gb(input_path)
            compressed_size = self._get_file_size_gb(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            
            self.logger.info(f"Compression complete:")
            self.logger.info(f"  Original size: {original_size:.2f} GB")
            self.logger.info(f"  Compressed size: {compressed_size:.2f} GB")
            self.logger.info(f"  Size reduction: {compression_ratio:.1f}%")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Video compression failed: {e}")
            return False
    
    def _check_and_compress_video(self, video_path: str) -> str:
        """Check video size and compress if larger than 15GB. Returns path to final video."""
        try:
            file_size_gb = self._get_file_size_gb(video_path)
            self.logger.info(f"Video file size: {file_size_gb:.2f} GB")
            
            # Rumble limit is 15GB
            if file_size_gb <= 15.0:
                self.logger.info("Video size is within Rumble's 15GB limit")
                return video_path
            
            self.logger.warning(f"Video size ({file_size_gb:.2f} GB) exceeds Rumble's 15GB limit")
            
            # Create compressed filename
            video_path_obj = Path(video_path)
            compressed_path = video_path_obj.parent / f"{video_path_obj.stem}_compressed{video_path_obj.suffix}"
            
            # Compress video
            compression_success = self._compress_video(video_path, str(compressed_path), target_size_gb=14.0)
            
            if compression_success:
                # Verify compressed size
                compressed_size = self._get_file_size_gb(str(compressed_path))
                if compressed_size <= 15.0:
                    self.logger.info(f"✓ Video compressed successfully to {compressed_size:.2f} GB")
                    
                    # Replace original with compressed version
                    try:
                        shutil.move(str(compressed_path), video_path)
                        self.logger.info("✓ Replaced original video with compressed version")
                        return video_path
                    except Exception as e:
                        self.logger.error(f"Could not replace original video: {e}")
                        return str(compressed_path)
                else:
                    self.logger.warning(f"Compressed video ({compressed_size:.2f} GB) still too large")
                    # Clean up compressed file if it's still too large
                    try:
                        Path(compressed_path).unlink()
                    except:
                        pass
                    return video_path
            else:
                self.logger.error("Video compression failed, using original video")
                return video_path
                
        except Exception as e:
            self.logger.error(f"Error checking/compressing video: {e}")
            return video_path