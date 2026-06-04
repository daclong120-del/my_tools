import sys
import os
import time
from playwright.sync_api import sync_playwright

def is_socialpeta_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return "socialpeta.com" in u or "guangdada.com" in u

def main():
    port = 9222
    print(f"[*] Connecting to Chrome on port {port} with timeout=2000...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=2000)
            print(f"[+] Connected! Contexts count: {len(browser.contexts)}")
            if not browser.contexts:
                print("[-] No contexts found.")
                return
            context = browser.contexts[0]
            
            # Wait a bit for pages to sync
            print("[*] Waiting 1s for target sync...")
            time.sleep(1.0)
            
            print(f"[+] Pages count in context: {len(context.pages)}")
            for idx, page in enumerate(context.pages):
                url = page.url
                title = page.title()
                print(f"\n--- Page #{idx} ---")
                print(f"  URL: '{url}'")
                print(f"  Title: '{title}'")
                print(f"  Is SocialPeta URL: {is_socialpeta_url(url)}")
                
                try:
                    client = context.new_cdp_session(page)
                    target_info = client.send("Target.getTargetInfo")
                    target_id = target_info.get("targetInfo", {}).get("targetId")
                    print(f"  CDP targetId: '{target_id}'")
                except Exception as e:
                    print(f"  Failed to get CDP session / target info: {e}")
                    
            browser.close()
        except Exception as e:
            print(f"[-] Global connection error: {e}")

if __name__ == "__main__":
    main()
