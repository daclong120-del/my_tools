import os
import sys
import json
import asyncio
import requests
import ctypes

# Add tools to path to allow importing local services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
from socialpeta_downloader.core.utils import UtilsService

# Import websockets
import websockets

async def run_ws_sniffer_10_pages():
    print("[*] Starting raw WebSocket 10-Page CDP Sniffer...")
    
    # 1. Restore Chrome window using Win32 API
    try:
        hwnd = ctypes.windll.user32.FindWindowW("Chrome_WidgetWin_1", None)
        if hwnd:
            print("[*] Restoring and focusing Chrome window...")
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"[-] Could not restore Chrome window: {e}")
        
    await asyncio.sleep(1.0)
    
    # 2. Find target tab debugger WebSocket URL
    ws_url = None
    target_title = None
    try:
        resp = requests.get("http://127.0.0.1:9222/json/list", timeout=3)
        pages = resp.json()
        for p in pages:
            url = p.get("url", "").lower()
            title = p.get("title", "").lower()
            if p.get("type") == "page" and ("socialpeta" in url or "guangdada" in url or "socialpeta" in title or "guangdada" in title):
                ws_url = p.get("webSocketDebuggerUrl")
                target_title = p.get("title")
                print(f"[+] Found Target: Title='{target_title}', URL='{p.get('url')}'")
                break
    except Exception as e:
        print(f"[-] Error querying HTTP json list: {e}")
        return
        
    if not ws_url:
        print("[-] SocialPeta tab not found in Chrome. Please make sure it is open.")
        return
        
    utils = UtilsService()
    all_unique_items = {}
    
    print(f"[*] Connecting to WebSocket: {ws_url}")
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        # Enable domains
        await ws.send(json.dumps({"id": 1, "method": "Network.enable", "params": {}}))
        await ws.send(json.dumps({"id": 2, "method": "Page.enable", "params": {}}))
        
        # We start by reloading the page to capture the first page cleanly
        print("\n[*] Reloading page to start from Page 1...")
        await ws.send(json.dumps({"id": 3, "method": "Page.reload", "params": {}}))
        
        for current_page in range(1, 11):
            print(f"\n=================== PAGE {current_page} / 10 ===================")
            print(f"[*] Waiting for Page {current_page} API network response...")
            
            matched_req_id = None
            captured_json = None
            
            # Event loop to wait for this page's creative list response
            timeout_seconds = 20.0
            start_time = asyncio.get_event_loop().time()
            
            try:
                while True:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed >= timeout_seconds:
                        raise asyncio.TimeoutError()
                        
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds - elapsed)
                    data = json.loads(msg)
                    
                    method = data.get("method")
                    params = data.get("params", {})
                    
                    if method == "Network.responseReceived":
                        resp_data = params.get("response", {})
                        url = resp_data.get("url", "")
                        if ("/creative/list" in url and "list-condition" not in url) or "/creative-rank/list" in url:
                            matched_req_id = params.get("requestId")
                            print(f"[+] API response headers received (ID: {matched_req_id})")
                            
                    elif method == "Network.loadingFinished" and matched_req_id:
                        req_id = params.get("requestId")
                        if req_id == matched_req_id:
                            print(f"[+] API response loading finished. Requesting body...")
                            await ws.send(json.dumps({
                                "id": 100 + current_page,
                                "method": "Network.getResponseBody",
                                "params": {"requestId": req_id}
                            }))
                            
                    elif data.get("id") == 100 + current_page:
                        if "error" in data:
                            print(f"[-] Error getting response body: {data['error']}")
                            matched_req_id = None # Reset to try to capture another if available
                        else:
                            result = data.get("result", {})
                            body = result.get("body", "")
                            if body:
                                try:
                                    captured_json = json.loads(body)
                                    print("[+] Successfully captured response JSON payload.")
                                    break
                                except Exception as e_json:
                                    print(f"[-] Error decoding JSON body: {e_json}")
            except asyncio.TimeoutError:
                print(f"[-] Timeout waiting for Page {current_page} data.")
                if current_page == 1:
                    print("[-] Failed to capture Page 1. Aborting.")
                    return
                else:
                    print("[*] No network packet captured for this click. Ending crawl.")
                    break
                    
            if not captured_json:
                print(f"[-] Failed to extract JSON payload for Page {current_page}.")
                break
                
            # Parse creatives
            raw_items = utils._recursive_find_creatives(captured_json)
            page_items = []
            for item in raw_items:
                parsed = utils._parse_creative_item(item)
                if parsed.get("ad_id"):
                    page_items.append(parsed)
                    
            # Add to main dict
            new_discovered = 0
            for item in page_items:
                ad_id = item["ad_id"]
                if ad_id not in all_unique_items:
                    all_unique_items[ad_id] = item
                    new_discovered += 1
                    
            print(f"[+] Page {current_page} parsed: Found {len(page_items)} creatives ({new_discovered} new, {len(all_unique_items)} cumulative unique).")
            
            # If we reached Page 10, do not click Next Page
            if current_page == 10:
                print("[*] Reached target Page 10. Completed.")
                break
                
            # Click the Next Page button
            print("[*] Clicking 'Next Page' button via Page JS Evaluation...")
            click_expr = """
            (() => {
              const nextSelectors = [
                "li.ant-pagination-next",
                ".ant-pagination-next button",
                "button.btn-next",
                "li.btn-next"
              ];
              for (const sel of nextSelectors) {
                const btn = document.querySelector(sel);
                if (btn) {
                  if (btn.disabled || btn.classList.contains('is-disabled') || btn.getAttribute('aria-disabled') === 'true') {
                    return "disabled";
                  }
                  btn.scrollIntoView({ block: "center", behavior: "smooth" });
                  btn.click();
                  return "clicked";
                }
              }
              return "not_found";
            })()
            """
            
            await ws.send(json.dumps({
                "id": 200 + current_page,
                "method": "Runtime.evaluate",
                "params": {"expression": click_expr}
            }))
            
            # Wait for click status response
            click_status = "unknown"
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    data = json.loads(msg)
                    if data.get("id") == 200 + current_page:
                        result = data.get("result", {})
                        click_status = result.get("result", {}).get("value", "unknown")
                        break
            except Exception as e_click:
                print(f"[-] Click evaluation timed out or erred: {e_click}")
                
            print(f"[+] Next Page click evaluation result: '{click_status}'")
            if click_status == "disabled":
                print("[*] 'Next Page' button is disabled. Reached the last page. Stopping crawl.")
                break
            elif click_status == "not_found":
                print("[-] Could not find 'Next Page' button. Stopping crawl.")
                break
                
            # Short sleep to let the UI update and trigger network request
            await asyncio.sleep(2.0)
            
    print("\n=================== CRAWL COMPLETE ===================")
    print(f"[+] Total unique creative items captured across all pages: {len(all_unique_items)}")
    
    # Save results to discovered_creatives_10_pages.json
    out_file = "test_env/discovered_creatives_10_pages.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(list(all_unique_items.values()), f, ensure_ascii=False, indent=2)
    print(f"[+] Saved all {len(all_unique_items)} items to {out_file}")

if __name__ == '__main__':
    asyncio.run(run_ws_sniffer_10_pages())
