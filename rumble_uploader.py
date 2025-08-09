#!/usr/bin/env python3
import os
import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError
import config  # must define RUMBLE_EMAIL & RUMBLE_PASSWORD

logger = logging.getLogger(__name__)
UPLOAD_URL = "https://rumble.com/upload.php"

def upload_to_rumble(video_path: str, title: str, description: str, tags: list[str]):
    logger.info(f"→ Rumble: uploading {os.path.basename(video_path)}")
    
    # Get file size for logging
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    logger.info(f"  • File size: {file_size_mb:.1f} MB")
    
    user_data = os.path.join(os.getcwd(), "pw-profile")

    with sync_playwright() as p:
        # Keep headless=False for debugging
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=user_data, 
            headless=False,
            args=['--disable-blink-features=AutomationControlled']  # Avoid detection
        )
        page = ctx.new_page()

        try:
            # 1) Go to upload page
            logger.info("  • Navigating to upload page...")
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            
            # Take a screenshot for debugging
            page.screenshot(path="rumble_debug_1.png")
            logger.info(f"  • Current URL: {page.url}")

            # 2) Check if we need to login
            if "auth.rumble.com" in page.url or page.locator('input[name="email"]').is_visible():
                logger.info("  • Login required, attempting to log in...")
                
                try:
                    page.wait_for_selector('input[name="email"]', timeout=10000)
                    page.fill('input[name="email"]', config.RUMBLE_EMAIL)
                    page.fill('input[name="password"]', config.RUMBLE_PASSWORD)
                    
                    # Try different login button selectors
                    login_selectors = [
                        'button#login-submit',
                        'input[type="submit"]',
                        'button[type="submit"]',
                        '.login-submit'
                    ]
                    
                    for selector in login_selectors:
                        if page.locator(selector).is_visible():
                            page.click(selector)
                            break
                    else:
                        logger.error("  ❌ Could not find login button")
                        return False
                    
                    # Wait for redirect back to upload page
                    page.wait_for_url("**/upload.php", timeout=30000)
                    logger.info("  ✓ Successfully logged in")
                    
                except TimeoutError as e:
                    logger.error(f"  ❌ Login failed: {e}")
                    page.screenshot(path="rumble_login_error.png")
                    return False

            # 3) Look for file upload input
            logger.info("  • Looking for file upload input...")
            
            # Try multiple possible selectors for the file input
            file_selectors = [
                '#Filedata',
                'input[type="file"]',
                'input[name="file"]',
                '.file-input'
            ]
            
            file_input = None
            for selector in file_selectors:
                try:
                    if page.locator(selector).is_visible():
                        file_input = selector
                        break
                except:
                    continue
            
            if not file_input:
                logger.error("  ❌ Could not find file upload input")
                page.screenshot(path="rumble_no_file_input.png")
                logger.info(f"  • Page content: {page.content()[:500]}...")
                return False

            # 4) Upload the file - NO TIMEOUTS for large files!
            logger.info(f"  • Uploading file using selector: {file_input}")
            logger.info(f"  • This may take a while for large files ({file_size_mb:.1f} MB)...")
            
            page.set_input_files(file_input, video_path)
            
            # Wait for upload progress - with patience for large files
            upload_success = False
            last_progress_log = time.time()
            progress_check_interval = 30  # Log progress every 30 seconds
            
            logger.info("  • Upload started - waiting for completion (no timeout)...")
            
            while not upload_success:
                try:
                    # Check if upload is complete using multiple methods
                    
                    # Method 1: Check for 100% progress
                    progress_element = page.locator('.num_percent').first
                    if progress_element.is_visible():
                        progress_text = progress_element.inner_text()
                        if '100%' in progress_text:
                            upload_success = True
                            logger.info("  ✓ Upload completed (100% progress detected)")
                            break
                        
                        # Log progress periodically
                        if time.time() - last_progress_log > progress_check_interval:
                            logger.info(f"  • Upload progress: {progress_text}")
                            last_progress_log = time.time()
                    
                    # Method 2: Check for form fields becoming available
                    if page.locator('#title').is_visible() and not upload_success:
                        # Double-check that we're not in an error state
                        if not page.locator('.error').is_visible():
                            upload_success = True
                            logger.info("  ✓ Upload completed (form fields available)")
                            break
                    
                    # Method 3: Check for progress bar
                    progress_bar = page.locator('.progress-bar').first
                    if progress_bar.is_visible():
                        width = progress_bar.evaluate("el => el.style.width")
                        if width and '100%' in width:
                            upload_success = True
                            logger.info("  ✓ Upload completed (progress bar at 100%)")
                            break
                    
                    # Wait before checking again
                    time.sleep(5)
                    
                    # Log a heartbeat every few minutes for very large files
                    if time.time() - last_progress_log > progress_check_interval:
                        logger.info("  • Still uploading... (checking progress)")
                        last_progress_log = time.time()
                    
                except Exception as e:
                    logger.warning(f"  • Error checking upload progress: {e}")
                    time.sleep(10)  # Wait longer if there's an error
                    continue

            # Give it extra time to process after upload
            logger.info("  • Upload complete, processing...")
            time.sleep(15)

            # 5) Fill metadata
            logger.info("  • Filling metadata...")
            
            try:
                # Fill title
                if page.locator("#title").is_visible():
                    page.fill("#title", title)
                    logger.info("  ✓ Title filled")
                else:
                    logger.warning("  ⚠ Title field not found")

                # Fill description
                if page.locator("#description").is_visible():
                    page.fill("#description", description)
                    logger.info("  ✓ Description filled")
                else:
                    logger.warning("  ⚠ Description field not found")

                # Fill tags
                if page.locator("#tags").is_visible():
                    page.fill("#tags", ",".join(tags))
                    logger.info("  ✓ Tags filled")
                else:
                    logger.warning("  ⚠ Tags field not found")

            except Exception as e:
                logger.error(f"  ❌ Error filling metadata: {e}")
                page.screenshot(path="rumble_metadata_error.png")

            # 6) Categories
            logger.info("  • Setting categories...")
            try:
                # Primary category
                if page.locator("input[name='primary-category']").is_visible():
                    page.click("input[name='primary-category']")
                    page.fill("input[name='primary-category']", "Entertainment")
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    logger.info("  ✓ Primary category set")

                # Secondary category
                if page.locator("input[name='secondary-category']").is_visible():
                    page.click("input[name='secondary-category']")
                    page.fill("input[name='secondary-category']", "Wild Wildlife")
                    time.sleep(1)
                    page.keyboard.press("Enter")
                    logger.info("  ✓ Secondary category set")
                    
            except Exception as e:
                logger.warning(f"  ⚠ Category setting failed: {e}")

            # 7) Agree to terms
            logger.info("  • Agreeing to terms...")
            try:
                # Try different checkbox selectors
                rights_selectors = ["input#crights", "input[name='rights']", "input[type='checkbox'][name*='rights']"]
                terms_selectors = ["input#cterms", "input[name='terms']", "input[type='checkbox'][name*='terms']"]
                
                for selector in rights_selectors:
                    if page.locator(selector).is_visible():
                        page.check(selector)
                        logger.info("  ✓ Rights checkbox checked")
                        break
                        
                for selector in terms_selectors:
                    if page.locator(selector).is_visible():
                        page.check(selector)
                        logger.info("  ✓ Terms checkbox checked")
                        break
                        
            except Exception as e:
                logger.warning(f"  ⚠ Terms agreement failed: {e}")

            # 8) Submit
            logger.info("  • Submitting form...")
            try:
                submit_selectors = [
                    "input#submitForm2",
                    "button[type='submit']",
                    "input[type='submit']",
                    ".submit-btn"
                ]
                
                submitted = False
                for selector in submit_selectors:
                    if page.locator(selector).is_visible():
                        page.click(selector)
                        submitted = True
                        logger.info(f"  ✓ Form submitted using {selector}")
                        break
                
                if not submitted:
                    logger.error("  ❌ Could not find submit button")
                    page.screenshot(path="rumble_no_submit.png")
                    return False
                    
                # Wait for the submission to process
                logger.info("  • Processing submission...")
                time.sleep(10)
                logger.info("  ✓ Rumble upload completed successfully")
                return True
                
            except Exception as e:
                logger.error(f"  ❌ Form submission failed: {e}")
                page.screenshot(path="rumble_submit_error.png")
                return False

        except Exception as e:
            logger.error(f"  ❌ Rumble upload failed: {e}")
            page.screenshot(path="rumble_general_error.png")
            return False
            
        finally:
            ctx.close()

    return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload a video to Rumble")
    parser.add_argument("video_path", help="Path to the video file")
    parser.add_argument("title", help="Video title")
    parser.add_argument("description", help="Video description")
    parser.add_argument("--tags", nargs='*', default=[], help="List of tags for the video")
    
    args = parser.parse_args()
    
    success = upload_to_rumble(args.video_path, args.title, args.description, args.tags)
    if success:
        print("Upload successful!")
    else:
        print("Upload failed.")

