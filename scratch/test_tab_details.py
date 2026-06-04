import sys
import os
import time
from playwright.sync_api import sync_playwright

def main():
    port = 9222
    print(f"[*] Connecting to Chrome on port {port}...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}")
            print(f"[+] Connected successfully! Contexts count: {len(browser.contexts)}")
            if not browser.contexts:
                print("[-] No contexts found.")
                return
            context = browser.contexts[0]
            print(f"[+] Pages count: {len(context.pages)}")
            for idx, page in enumerate(context.pages):
                print(f"  Page {idx}: Title='{page.title()}', URL='{page.url}'")
                
                # Let's listen to responses on the first SocialPeta page we find
                if "socialpeta.com" in page.url or "guangdada.com" in page.url:
                    print(f"[*] Attaching response listener to Page {idx}...")
                    
                    def handle_response(response):
                        url = response.url
                        if "list" in url or "creative" in url or "api" in url:
                            print(f"    [Response] Status: {response.status}, URL: {url}")
                            try:
                                # Try to print a sample of the JSON structure if it is a JSON response
                                if "json" in response.headers.get("content-type", ""):
                                    print(f"               JSON keys: {list(response.json().keys())}")
                            except Exception as ex:
                                print(f"               Error reading JSON: {ex}")
                                
                    page.on("response", handle_response)
                    
                    print("[*] Listening for 10 seconds. Try scrolling the page on your browser to trigger requests...")
                    for i in range(10):
                        time.sleep(1.0)
                        
                    page.remove_listener("response", handle_response)
                    break
            browser.close()
        except Exception as e:
            print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
