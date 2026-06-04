import sys
import os
import time
from playwright.sync_api import sync_playwright

def main():
    port = 9222
    print(f"[*] Connecting to Chrome on port {port}...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=2000)
            context = browser.contexts[0]
            
            for attempt in range(10):
                print(f"\n--- Attempt #{attempt} (time: {time.time():.2f}) ---")
                pages = context.pages
                print(f"Pages count: {len(pages)}")
                for idx, page in enumerate(pages):
                    print(f"  Page #{idx}: URL='{page.url}'")
                time.sleep(0.5)
                
            browser.close()
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
