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
            print(f"[+] Connected! Pages count: {len(context.pages)}")
            
            for idx, page in enumerate(context.pages):
                print(f"\n--- Page #{idx} ---")
                print(f"  Top URL: '{page.url}'")
                print(f"  Frames count: {len(page.frames)}")
                for f_idx, frame in enumerate(page.frames):
                    print(f"    Frame #{f_idx}: Name='{frame.name}', URL='{frame.url}'")
                    
            browser.close()
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
