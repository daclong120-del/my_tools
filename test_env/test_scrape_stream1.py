import os
import sys
import time
import json
import requests
import traceback
from playwright.sync_api import sync_playwright

# Add tools to path to allow importing local services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
from socialpeta_downloader.core.utils import UtilsService

def test_stream1_scraping():
    print("[*] Starting test_stream1_scraping...")
    
    # Restore Chrome using Win32 API if minimized
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW("Chrome_WidgetWin_1", None)
        if hwnd:
            print("[*] Restoring Chrome window via Win32 ShowWindow...")
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            print("[*] Set Chrome window to foreground.")
    except Exception as e_restore:
        print(f"[-] Could not restore Chrome window: {e_restore}")

    # Instantiate UtilsService
    utils = UtilsService()
    
    # Activate Chrome window (fallback)
    utils.bring_chrome_to_foreground()
    
    # Give the browser window a moment to wake up and resume renderers
    print("[*] Sleeping 2 seconds to allow renderers to resume...")
    time.sleep(2.0)

    # Pre-query tabs via HTTP to find SocialPeta
    target_info = None
    try:
        resp = requests.get("http://127.0.0.1:9222/json/list", timeout=3)
        pages = resp.json()
        for p_info in pages:
            url = p_info.get("url", "").lower()
            title = p_info.get("title", "").lower()
            if p_info.get("type") == "page" and ("socialpeta" in url or "guangdada" in url or "socialpeta" in title or "guangdada" in title):
                target_info = p_info
                print(f"[+] Found SocialPeta tab via HTTP: Title='{p_info.get('title')}', URL='{p_info.get('url')}'")
                break
    except Exception as e:
        print(f"[-] Error querying HTTP json list: {e}")

    captured_data = []

    def handle_response(response):
        url = response.url
        if "/creative/list" in url or "/creative-rank/list" in url:
            print(f"[+] Sniffed matching API response: {url}")
            try:
                body = response.json()
                captured_data.append(body)
                print(f"[+] Successfully captured JSON response.")
            except Exception as e:
                print(f"[-] Error extracting JSON from response: {e}")

    with sync_playwright() as p:
        try:
            print("[*] Connecting to Chrome on debug port 9222...")
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222", timeout=5000)
            if not browser or not browser.contexts:
                print("[-] Failed to find active browser context.")
                return
            
            context = browser.contexts[0]
            
            # Find matching page in context.pages without calling new_page()
            target_page = None
            for idx, pg in enumerate(context.pages):
                try:
                    url = pg.url or ""
                    title = pg.title() or ""
                    print(f"  Tab {idx}: Title='{title}', URL='{url}'")
                    # If we matched via HTTP target_info, match by URL
                    if target_info and target_info.get("url") in url:
                        target_page = pg
                        break
                    # Fallback string match
                    if ("socialpeta" in url.lower() or "guangdada" in url.lower() or 
                        "socialpeta" in title.lower() or "guangdada" in title.lower()):
                        target_page = pg
                        break
                except Exception:
                    pass
            
            if not target_page:
                print("[-] Could not find any active SocialPeta tab in context.pages.")
                return
                
            print(f"[+] Hooked target page: Title='{target_page.title()}', URL='{target_page.url}'")
            
            # Ensure the page is in front and active
            target_page.bring_to_front()
            
            # Hook the response listener
            target_page.on("response", handle_response)
            
            # Trigger scrolling End and Home to initiate API request
            print("[*] Performing Soft Trigger scroll events...")
            target_page.keyboard.press("End")
            time.sleep(1.2)
            target_page.keyboard.press("Home")
            time.sleep(1.2)
            
            # If nothing was captured, try clicking search button
            if not captured_data:
                print("[*] No packets captured yet. Trying to click search button...")
                search_selectors = [
                    "button.ant-btn-primary:has-text('Search')",
                    "button.el-button--primary:has-text('Tìm kiếm')",
                    "button:has-text('Search')",
                    "button:has-text('Tìm kiếm')",
                    ".search-btn",
                    ".search-button"
                ]
                for sel in search_selectors:
                    try:
                        loc = target_page.locator(sel).first
                        if loc.count() > 0:
                            loc.scroll_into_view_if_needed(timeout=1000)
                            loc.click(timeout=2000)
                            print(f"[+] Clicked search button: {sel}")
                            time.sleep(3.0)
                            break
                    except Exception:
                        pass
            
            # Wait for packet
            print("[*] Waiting up to 10 seconds for API packets to be captured...")
            for i in range(10):
                if captured_data:
                    break
                time.sleep(1.0)
                
            if not captured_data:
                print("[-] Failed to capture any /creative/list response packets.")
                return
                
            # Process captured data
            print("[*] Parsing items from captured packets...")
            all_parsed_items = []
            for idx, body in enumerate(captured_data):
                raw_items = utils._recursive_find_creatives(body)
                print(f"  Packet {idx + 1}: Found {len(raw_items)} raw items.")
                for item in raw_items:
                    parsed = utils._parse_creative_item(item)
                    all_parsed_items.append(parsed)
            
            # De-duplicate items by ad_id
            unique_items = {}
            for item in all_parsed_items:
                ad_id = item.get("ad_id")
                if ad_id and ad_id not in unique_items:
                    unique_items[ad_id] = item
                    
            print(f"\n[+] SUCCESS: Discovered {len(unique_items)} unique creative items on the page!")
            
            # Print details of the first 10 items
            print("\n--- First 10 Items Snippet ---")
            for idx, (ad_id, item) in enumerate(list(unique_items.items())[:10]):
                print(f"{idx + 1}. ID: {ad_id}")
                print(f"   App Name: {item.get('app_name')}")
                print(f"   Media Type: {item.get('media_type')}")
                print(f"   Platform: {item.get('platform')}")
                print(f"   Video URL: {item.get('video_url')[:80]}..." if item.get('video_url') else "   Video URL: None")
                print(f"   Image URL: {item.get('image_url')[:80]}..." if item.get('image_url') else "   Image URL: None")
                print("-" * 30)
                
            # Save the full results to a JSON file
            out_file = "test_env/discovered_creatives.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(list(unique_items.values()), f, ensure_ascii=False, indent=2)
            print(f"[+] Saved all {len(unique_items)} parsed items to {out_file}")
            
        except Exception as e:
            print(f"[-] Execution Error: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    test_stream1_scraping()
