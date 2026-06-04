# scratch/debug_chrome_launch.py
import os
import sys
import subprocess
import time
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from socialpeta_downloader.config import settings

def test():
    # 1. Resolve path
    chrome_path = None
    if os.name == 'nt':
        try:
            import winreg
            for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    with winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                        path, _ = winreg.QueryValueEx(key, "")
                        if path and os.path.exists(path):
                            chrome_path = path
                            break
                except Exception:
                    continue
        except Exception:
            pass
            
        if not chrome_path:
            standard_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            for path in standard_paths:
                if os.path.exists(path):
                    chrome_path = path
                    break
    
    print(f"Resolved Chrome path: {chrome_path}")
    if not chrome_path or not os.path.exists(chrome_path):
        print("Chrome path not found!")
        return

    # Try launching without DETACHED_PROCESS to capture output/errors
    chrome_profile_dir = os.path.join(settings.DATA_DIR, "chrome_debug_profile_test")
    os.makedirs(chrome_profile_dir, exist_ok=True)
    
    port = 9333
    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={chrome_profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-timer-throttling",
        "about:blank"
    ]
    
    print(f"Running command: {cmd}")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Process started. Waiting 3 seconds...")
        time.sleep(3)
        
        # Check port
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=2.0)
            print(f"Response from Chrome: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Failed to query port: {e}")
            
        # Poll process status
        poll = proc.poll()
        if poll is not None:
            print(f"Process exited with code: {poll}")
            stdout, stderr = proc.communicate()
            print(f"Stdout: {stdout.decode(errors='ignore')}")
            print(f"Stderr: {stderr.decode(errors='ignore')}")
        else:
            print("Process is still running. Terminating...")
            proc.terminate()
    except Exception as e:
        print(f"Launch failed with error: {e}")

if __name__ == "__main__":
    test()
