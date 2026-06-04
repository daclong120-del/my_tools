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
            
            target_page = None
            for idx, page in enumerate(context.pages):
                try:
                    client = context.new_cdp_session(page)
                    target_info = client.send("Target.getTargetInfo")
                    target_id = target_info.get("targetInfo", {}).get("targetId")
                    if target_id == '391F4805B90E896C523EF615137B9413':
                        target_page = page
                        break
                except Exception:
                    pass
            
            if target_page:
                try:
                    target_page.set_default_timeout(3000)
                    print("[*] Evaluating window.location.href...")
                    url = target_page.evaluate("window.location.href")
                    print(f"[SUCCESS] evaluated URL: '{url}'")
                except Exception as e:
                    print(f"[-] Evaluation failed: {e}")
            else:
                print("[-] Target page not found.")
                
            browser.close()
        except Exception as e:
            print(f"[-] Global error: {e}")

if __name__ == "__main__":
    main()
