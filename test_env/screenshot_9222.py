import os
import sys
import time
from playwright.sync_api import sync_playwright

def main():
    print("[*] Connecting to Chrome over CDP on port 9222...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            if not browser.contexts:
                print("[-] No browser contexts found.")
                return
            context = browser.contexts[0]
            pages = context.pages
            print(f"[+] Found {len(pages)} pages:")
            selected_page = None
            for i, page in enumerate(pages):
                try:
                    url = page.url
                    title = page.title()
                    print(f"  Page {i}: URL='{url}' Title='{title}'")
                    if "socialpeta" in url or "guangdada" in url:
                        selected_page = page
                except Exception as e_page:
                    print(f"  Page {i} error: {e_page}")
            
            if selected_page:
                print(f"[+] Found SocialPeta page. Taking screenshot...")
                try:
                    selected_page.bring_to_front()
                except Exception:
                    pass
                time.sleep(2)
                screenshot_path = os.path.abspath("screenshot_socialpeta.png")
                selected_page.screenshot(path=screenshot_path)
                print(f"[+] Screenshot saved to {screenshot_path}")
            else:
                print("[-] No active SocialPeta page found.")
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
