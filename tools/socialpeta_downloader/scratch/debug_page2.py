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
            
            # Scroll down to page bottom
            print("[*] Scrolling to bottom...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            page_num = 4
            selectors = [
                f"li.ant-pagination-item-{page_num}",
                f"ul.ant-pagination li.ant-pagination-item-{page_num}",
                f"ul.el-pagination li.number:has-text('{page_num}')",
                f".el-pagination li:has-text('{page_num}')",
                f"//li[contains(@class, 'number') and text()='{page_num}']",
                f"button:has-text('{page_num}')",
                f"li:has-text('{page_num}')"
            ]
            
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    cnt = loc.count()
                    if cnt > 0:
                        text = loc.text_content()
                        html = loc.evaluate("el => el.outerHTML")
                        print(f"[*] Selector '{sel}' matches element. Text: '{text}', HTML: {html[:200]}")
                except Exception as e:
                    print(f"[-] Selector '{sel}' error: {e}")
                    
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
