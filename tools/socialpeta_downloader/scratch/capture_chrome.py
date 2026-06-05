import sys
import os
from playwright.sync_api import sync_playwright

# Add paths
scripts_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.dirname(os.path.dirname(scripts_dir))
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore(skip_db_init=True)
    with sync_playwright() as p:
        try:
            browser, page = core.connect_to_active_tab(p, port=9222)
            if page:
                screenshot_path = os.path.abspath("chrome_screenshot.png")
                page.screenshot(path=screenshot_path)
                print(f"[+] Screenshot captured and saved to: {screenshot_path}")
                print(f"[+] Current Page URL: {page.url}")
                print(f"[+] Page Title: {page.title()}")
            else:
                print("[-] Could not connect to active SocialPeta tab.")
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
