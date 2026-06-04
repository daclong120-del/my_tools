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
                url = page.url
                print(f"\n--- Page #{idx} ---")
                print(f"  URL: '{url}'")
                
                try:
                    # Let's try creating a CDP session
                    print("  Creating CDP session...")
                    client = context.new_cdp_session(page)
                    print("  Sending Target.getTargetInfo...")
                    target_info = client.send("Target.getTargetInfo")
                    target_id = target_info.get("targetInfo", {}).get("targetId")
                    print(f"  [SUCCESS] targetId: '{target_id}'")
                except Exception as e:
                    print(f"  [ERROR] Failed: {e}")
                    
            browser.close()
        except Exception as e:
            print(f"[-] Global error: {e}")

if __name__ == "__main__":
    main()
