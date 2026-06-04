import asyncio
import json
import websockets

async def test_cdp():
    ws_url = "ws://localhost:9222/devtools/page/391F4805B90E896C523EF615137B9413"
    print(f"[*] Connecting to raw WebSocket: {ws_url}...")
    try:
        async with websockets.connect(ws_url) as ws:
            print("[+] Connected!")
            
            # Enable Runtime
            print("[*] Sending Runtime.enable...")
            await ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.enable"
            }))
            resp = await ws.recv()
            print(f"[+] Runtime.enable response: {resp}")
            
            # Evaluate window.location.href
            print("[*] Sending Runtime.evaluate...")
            await ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "window.location.href"
                }
            }))
            resp = await ws.recv()
            print(f"[+] Runtime.evaluate response: {resp}")
            
    except Exception as e:
        print(f"[-] Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_cdp())
