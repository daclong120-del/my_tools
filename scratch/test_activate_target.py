import sys
import os
import time
from playwright.sync_api import sync_playwright

def main():
    port = 9222
    target_id = '391F4805B90E896C523EF615137B9413'
    print(f"[*] Connecting to Chrome on port {port}...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=2000)
            context = browser.contexts[0]
            
            # Send activateTarget via browser CDP session
            client = browser.new_browser_cdp_session()
            print(f"[*] Activating target {target_id}...")
            client.send("Target.activateTarget", {"targetId": target_id})
            print("[+] Target activated!")
            
            print("[*] Waiting 2 seconds for tab to wake up and sync...")
            time.sleep(2.0)
            
            # Now let's check pages
            print(f"[+] Pages count: {len(context.pages)}")
            for idx, page in enumerate(context.pages):
                try:
                    c = context.new_cdp_session(page)
                    t_info = c.send("Target.getTargetInfo")
                    t_id = t_info.get("targetInfo", {}).get("targetId")
                    if t_id == target_id:
                        print(f"  [FOUND] Page #{idx}: URL='{page.url}'")
                        
                        # Let's try a safe evaluate now
                        print("  Trying safe evaluate...")
                        page.set_default_timeout(2000)
                        title = page.evaluate("document.title")
                        print(f"  [SUCCESS] Evaluated title: '{title}'")
                except Exception as e:
                    print(f"  [-] Page #{idx} error: {e}")
                    
            browser.close()
        except Exception as e:
            print(f"[-] Global error: {e}")

if __name__ == "__main__":
    main()
