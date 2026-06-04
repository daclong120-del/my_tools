import asyncio
import json
import websockets

async def test_cdp():
    ws_url = "ws://localhost:9222/devtools/page/391F4805B90E896C523EF615137B9413"
    print(f"[*] Connecting to raw WebSocket: {ws_url}...")
    try:
        async with websockets.connect(ws_url) as ws:
            print("[+] Connected!")
            
            # Send Runtime.enable
            print("[*] Sending Runtime.enable...")
            await ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.enable"
            }))
            
            # Send Runtime.evaluate
            print("[*] Sending Runtime.evaluate...")
            await ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "window.location.href"
                }
            }))
            
            # Poll for responses for 2 seconds
            print("[*] Polling messages for 2 seconds...")
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < 2.0:
                try:
                    resp_str = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    resp = json.loads(resp_str)
                    if "id" in resp:
                        print(f"[RESPONSE] ID {resp['id']}: {resp}")
                    else:
                        print(f"[EVENT] Method {resp.get('method')}: {resp}")
                except asyncio.TimeoutError:
                    pass
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_cdp())
