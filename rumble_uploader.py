import os, sys, time, argparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import config  # must define RUMBLE_EMAIL and RUMBLE_PASSWORD

UPLOAD_URL = "https://rumble.com/upload.php"

def upload_to_rumble(video_path, title, description, tags):

    with sync_playwright() as p:
        user_data = os.path.expanduser("./pw-profile")
        browser = p.chromium.launch_persistent_context(user_data_dir=user_data, headless=False)
        page = browser.new_page()
        page.goto(UPLOAD_URL)

        if "auth.rumble.com" in page.url:
            page.fill('input[name="username"]', config.RUMBLE_EMAIL)
            page.fill('input[name="password"]', config.RUMBLE_PASSWORD)
            page.click('button[type="submit"]')

        page.set_input_files("#Filedata", video_path)

        page.wait_for_function(
            """() => {
                const el = document.querySelector('.num_percent');
                return el && el.innerText.trim().startsWith('100%');
            }""",
            timeout=7200000
        )

        time.sleep(1)

        page.fill("#title", title)
        page.fill("#description", description)
        page.fill("#tags", ",".join(tags))

        page.click("input[name='primary-category']")
        page.fill("input[name='primary-category']", "Entertainment")
        page.keyboard.press("Enter")

        page.click("input[name='secondary-category']")
        page.fill("input[name='secondary-category']", "Wild Wildlife")
        page.keyboard.press("Enter")

        page.wait_for_selector(
            ".thumbContainers a:nth-of-type(3) img:not([src='/i/t16x9.gif'])",
            timeout=120000
        )

        submit_btn = page.locator("#submitForm")
        submit_btn.scroll_into_view_if_needed()
        submit_btn.click()

        submit2 = page.locator("input#submitForm2")
        submit2.scroll_into_view_if_needed()
        page.click("label[for='crights']")
        page.click("label[for='cterms']")
        submit2.click()

        page.wait_for_load_state("networkidle", timeout=100000)
        browser.close()

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Upload a video to Rumble.")
#     parser.add_argument("video_path", help="Path to the video file to upload")
#     parser.add_argument("--title", help="Title of the video")
#     parser.add_argument("--description", help="Description of the video")
#     parser.add_argument("--tags", nargs='*', help="Tags for the video")

#     args = parser.parse_args()

#     if not os.path.exists(args.video_path):
#         print(f"Error: Video file '{args.video_path}' does not exist.")
#         sys.exit(1)

#     upload_to_rumble(args.video_path, args.title, args.description, args.tags)
