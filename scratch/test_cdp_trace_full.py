import os
import sys
import time

# Set debug env var before importing playwright
os.environ["DEBUG"] = "pw:protocol"

# Redirect stdout to a log file
log_file = open("scratch/pw_protocol.log", "w", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

from playwright.sync_api import sync_playwright

def main():
    port = 9222
    target_id = '391F4805B90E896C523EF615137B9413'
    print(f"[*] Starting connection to port {port}...")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=2000)
            context = browser.contexts[0]
            print(f"[+] Connected! Pages count: {len(context.pages)}")
            
            # Wait 2 seconds to capture incoming events
            print("[*] Waiting 2 seconds...")
            time.sleep(2.0)
            
            # Print page URLs
            for idx, page in enumerate(context.pages):
                print(f"Page #{idx}: URL='{page.url}'")
                
            browser.close()
        except Exception as e:
            print(f"[-] Error: {e}")
            
    print("[*] Script finished.")
    log_file.close()

if __name__ == "__main__":
    main()
