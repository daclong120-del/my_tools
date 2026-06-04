import os
import sys
import json
import asyncio
import csv
import requests
import ctypes

# Add tools to path to allow importing local services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
from socialpeta_downloader.core.utils import UtilsService

# Import websockets
import websockets

async def run_ws_sniffer_current_page_csv():
    print("[*] Starting raw WebSocket 1-Page Current Tab Sniffer (CSV Output)...")
    
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
    captured_json = None
    
    print(f"[*] Connecting to WebSocket: {ws_url}")
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        # Enable domains
        await ws.send(json.dumps({"id": 1, "method": "Network.enable", "params": {}}))
        await ws.send(json.dumps({"id": 2, "method": "Page.enable", "params": {}}))
        
        # Reload current page to capture network packet
        print("\n[*] Reloading page to trigger API network response...")
        await ws.send(json.dumps({"id": 3, "method": "Page.reload", "params": {}}))
        
        matched_req_id = None
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
                            "id": 100,
                            "method": "Network.getResponseBody",
                            "params": {"requestId": req_id}
                        }))
                        
                elif data.get("id") == 100:
                    if "error" in data:
                        print(f"[-] Error getting response body: {data['error']}")
                        matched_req_id = None
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
            print("[-] Timeout waiting for network packet.")
            return
            
    if not captured_json:
        print("[-] Failed to capture page data.")
        return
        
    # Parse creatives
    raw_items = utils._recursive_find_creatives(captured_json)
    page_items = []
    for item in raw_items:
        parsed = utils._parse_creative_item(item)
        if parsed.get("ad_id"):
            page_items.append(parsed)
            
    print(f"[+] Parsed: Found {len(page_items)} creatives on this page.")
    
    # Save results to discovered_creatives_current_page.csv
    out_file = "test_env/discovered_creatives_current_page.csv"
    headers = [
        "ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
        "duration", "impression", "heat", "platform", "download_time", "publisher",
        "app_name", "area", "copywriting_language", "title", "body", "deployment_time",
        "saved_path", "file_size", "status"
    ]
    
    try:
        with open(out_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for item in page_items:
                row = {h: item.get(h, "") for h in headers}
                writer.writerow(row)
        print(f"[+] Saved all {len(page_items)} items to {out_file}")
    except Exception as e_csv:
        print(f"[-] Error writing CSV: {e_csv}")

if __name__ == '__main__':
    asyncio.run(run_ws_sniffer_current_page_csv())
