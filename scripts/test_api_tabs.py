import subprocess
import time
import sys
import os
import urllib.request
import json
import traceback

def test_api():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools_dir = os.path.join(root_dir, "tools")
    
    print("[*] Starting backend process...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "socialpeta_downloader.api"],
        cwd=tools_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(4)
    
    out_lines = []
    try:
        print("[*] Sending request to http://localhost:8003/api/v1/socialpeta/tabs...")
        req = urllib.request.Request("http://localhost:8003/api/v1/socialpeta/tabs")
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.status
            body = response.read().decode('utf-8')
            out_lines.append(f"[+] HTTP Status: {status}")
            out_lines.append(f"[+] Response body: {body}")
            
    except Exception as e:
        tb = traceback.format_exc()
        out_lines.append(f"[-] Error calling API: {e}\n{tb}")
    finally:
        print("[*] Stopping backend process...")
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
            
    with open("test_api_tabs_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("[*] Wrote results to test_api_tabs_output.txt")

if __name__ == '__main__':
    test_api()
