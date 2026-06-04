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
                # Find page by target ID matching the SocialPeta tab
                try:
                    client = context.new_cdp_session(page)
                    target_info = client.send("Target.getTargetInfo")
                    target_id = target_info.get("targetInfo", {}).get("targetId")
                    if target_id == '391F4805B90E896C523EF615137B9413':
                        target_page = page
                        print(f"[+] Found SocialPeta page! URL before bring_to_front: '{page.url}'")
                        break
                except Exception:
                    pass
            
            if target_page:
                try:
                    print("[*] Calling bring_to_front()...")
                    target_page.bring_to_front()
                    print("[+] bring_to_front() succeeded!")
                    
                    print("[*] Waiting 2 seconds...")
                    time.sleep(2.0)
                    print(f"[+] URL after waiting: '{target_page.url}'")
                except Exception as e:
                    print(f"[-] Failed during bring_to_front: {e}")
            else:
                print("[-] Target page not found.")
                
            browser.close()
        except Exception as e:
            print(f"[-] Global error: {e}")

if __name__ == "__main__":
    main()
