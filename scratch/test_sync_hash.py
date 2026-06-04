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
            
            target_page = None
            for idx, page in enumerate(context.pages):
                try:
                    c = context.new_cdp_session(page)
                    t_info = c.send("Target.getTargetInfo")
                    t_id = t_info.get("targetInfo", {}).get("targetId")
                    if t_id == target_id:
                        target_page = page
                        break
                except Exception:
                    pass
            
            if target_page:
                print(f"[+] Found page! Initial URL: '{target_page.url}'")
                
                # Create CDP session to evaluate hash change
                print("[*] Creating page-level CDP session...")
                client = context.new_cdp_session(target_page)
                
                print("[*] Triggering hash navigation via raw CDP evaluate...")
                client.send("Runtime.evaluate", {
                    "expression": "location.hash = '#sync_' + Date.now()"
                })
                
                print("[*] Waiting 1 second for Playwright to sync...")
                time.sleep(1.0)
                
                print(f"[+] URL after hash navigation: '{target_page.url}'")
                
                print("[*] Trying Playwright page.evaluate...")
                target_page.set_default_timeout(2000)
                title = target_page.evaluate("document.title")
                print(f"[SUCCESS] Evaluated title via Playwright: '{title}'")
            else:
                print("[-] Target page not found.")
                
            browser.close()
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
