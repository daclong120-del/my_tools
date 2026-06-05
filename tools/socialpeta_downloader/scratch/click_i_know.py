import sys
import os
import time
from playwright.sync_api import sync_playwright

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
            if not page:
                print("[-] Could not connect to active SocialPeta tab.")
                return
            
            print(f"[+] Connected to: {page.url}")
            
            # Look for "I know" button
            btn = page.locator("button:has-text('I know'), button:has-text('I Know'), .ant-btn-primary:has-text('I know')").first
            if btn.is_visible():
                print("[*] Clicking 'I know' button...")
                btn.click()
                time.sleep(3)
                page.screenshot(path="chrome_screenshot.png")
                print("[+] Saved chrome_screenshot.png after click")
            else:
                print("[-] 'I know' button not visible.")
                
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
