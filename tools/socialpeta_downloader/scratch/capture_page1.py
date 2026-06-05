import sys
import os
import json
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
            
            captured = []
            
            # Setup response handler
            def handle_response(response):
                url = response.url
                if "/creative/list" in url or "/creative-rank/list" in url:
                    print(f"\n[Network Log] URL: {url} (Status: {response.status})")
                    try:
                        data = response.json()
                        captured.append(data)
                        fpath = "captured_creative_response.json"
                        with open(fpath, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        print(f"[+] Saved response to {fpath}")
                    except Exception as e:
                        print(f"  --> Error reading JSON: {e}")
            
            page.on("response", handle_response)
            
            # Scroll down to page bottom
            print("[*] Scrolling to bottom...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Try to click Page 1 button
            print("[*] Clicking page 1...")
            nav_ok = core.utils_service._click_page_button(page, 1)
            print(f"[+] _click_page_button returned: {nav_ok}")
            
            # Wait for responses
            print("[*] Waiting for 10 seconds to capture network packets...")
            time.sleep(10)
            
            if not captured:
                print("[-] No creative list response was captured. Let's try soft trigger (reload Page 1)...")
                # Let's refresh page
                page.reload()
                time.sleep(10)
            
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
