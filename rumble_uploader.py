import os, sys, time, argparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import config  # must define RUMBLE_EMAIL and RUMBLE_PASSWORD

UPLOAD_URL = "https://rumble.com/upload.php"

def upload_to_rumble(video_path, title, description, tags):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(UPLOAD_URL)

        if "auth.rumble.com" in page.url:
            print("2. Logging in...")
            page.fill('input[name="username"]', config.RUMBLE_EMAIL)
            page.fill('input[name="password"]', config.RUMBLE_PASSWORD)
            page.click('button[type="submit"]')

        page.set_input_files("#Filedata", video_path)

        page.wait_for_function(
            """() => {
                const el = document.querySelector('.num_percent');
                return el && el.innerText.trim().startsWith('100%');
            }""",
            timeout=120000
        )

        time.sleep(1)

        page.fill("#title", title)
        page.fill("#description", description)
        page.fill("#tags", ", ".join(tags))

        page.fill("#primary-category", "Entertainment")
        page.fill("#secondary-category", "Wild Wildlife")

        page.wait_for_selector(
            ".thumbContainers a:nth-of-type(3) img:not([src='/i/t16x9.gif'])",
            timeout=120000
        )

        page.click("#submitForm")
        print("🚀 Upload clicked — waiting for completion…")

        try:
            page.wait_for_selector(".upload-complete, .upload-success", timeout=120000)
            print("✅ Upload finished!")
        except PlaywrightTimeout:
            print("⚠️ Still processing—please check your account.")

        browser.close()