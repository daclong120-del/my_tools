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

async def run_ws_sniffer():
    print("[*] Starting raw WebSocket CDP Sniffer...")
    
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
    matched_requests = {}
    
    print(f"[*] Connecting to WebSocket: {ws_url}")
    async with websockets.connect(ws_url) as ws:
        # Enable Network domain
        await ws.send(json.dumps({
            "id": 1,
            "method": "Network.enable",
            "params": {}
        }))
        
        # Enable Page domain
        await ws.send(json.dumps({
            "id": 2,
            "method": "Page.enable",
            "params": {}
        }))
        
        # Reload the page to force the Creative List API call
        print("[*] Sending Page.reload command to trigger fresh creative list fetch...")
        await ws.send(json.dumps({
            "id": 3,
            "method": "Page.reload",
            "params": {}
        }))
        
        print("[*] Waiting up to 15 seconds for network packets...")
        
        # Event loop to listen to CDP network events
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                data = json.loads(msg)
                
                method = data.get("method")
                params = data.get("params", {})
                
                if method == "Network.responseReceived":
                    resp_data = params.get("response", {})
                    url = resp_data.get("url", "")
                    
                    if ("/creative/list" in url and "list-condition" not in url) or "/creative-rank/list" in url:
                        req_id = params.get("requestId")
                        matched_requests[req_id] = url
                        print(f"[+] Response headers received: {url} | Request ID: {req_id}")
                        
                elif method == "Network.loadingFinished":
                    req_id = params.get("requestId")
                    if req_id in matched_requests:
                        url = matched_requests[req_id]
                        print(f"[+] Response loading finished for: {url}. Requesting body...")
                        await ws.send(json.dumps({
                            "id": 100,
                            "method": "Network.getResponseBody",
                            "params": {
                                "requestId": req_id
                            }
                        }))
                        
                elif data.get("id") == 100:
                    if "error" in data:
                        print(f"[-] Error from getResponseBody: {data['error']}")
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
            print("[-] Timeout waiting for network packets.")
            
    if not captured_json:
        print("[-] Failed to capture creative list data.")
        return
        
    print("[*] Parsing items from JSON payload...")
    raw_items = utils._recursive_find_creatives(captured_json)
    print(f"[+] Found {len(raw_items)} raw items in API response.")
    
    parsed_items = []
    for item in raw_items:
        parsed = utils._parse_creative_item(item)
        if parsed.get("ad_id"):
            parsed_items.append(parsed)
            
    # Deduplicate
    unique_items = {item["ad_id"]: item for item in parsed_items}
    print(f"\n[+] SUCCESS: Discovered {len(unique_items)} unique creative items on the page!")
    
    # Print details of the first 10 items
    print("\n--- Items Snippet ---")
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

if __name__ == '__main__':
    asyncio.run(run_ws_sniffer())
