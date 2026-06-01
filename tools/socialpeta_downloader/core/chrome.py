# tools/socialpeta_downloader/core/chrome.py
"""
Responsibility: Google Chrome Remote Debugging Port management and login verification.
"""

import os
import time
import socket
import subprocess
from typing import Optional
from playwright.sync_api import sync_playwright
from socialpeta_downloader.config import settings

class ChromeMixin:
    def ensure_chrome_debug_port(self, port: Optional[int] = None) -> bool:
        """
        Check if port is already open. If not, try to launch a local instance of Google
        Chrome with the remote debugging port enabled using a custom debug profile.
        """
        port = port if port is not None else settings.CHROME_DEBUG_PORT
            
        if self._is_chrome_cdp_active(port):
            return True
            
        print(f"[*] Chrome debug port {port} is not open. Attempting to launch Chrome...")
        
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
        else:
            import shutil
            chrome_path = shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("google-chrome-stable")
            
        if not chrome_path:
            print("[-] Google Chrome could not be found in standard locations.")
            return False
            
        # Launch with custom user data directory to run side-by-side with user's main Chrome without blocking
        chrome_profile_dir = os.path.join(settings.ROOT_DIR, "data", "chrome_debug_profile")
        os.makedirs(chrome_profile_dir, exist_ok=True)
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={chrome_profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank"
        ]
        
        try:
            print(f"[*] Launching Chrome debug on port {port} with profile: {chrome_profile_dir}")
            if os.name == 'nt':
                # DETACHED_PROCESS = 0x00000008
                subprocess.Popen(cmd, creationflags=0x00000008, close_fds=True)
            else:
                subprocess.Popen(cmd, start_new_session=True, close_fds=True)
                
            # Wait for port to open (up to 5 seconds, poll every 500ms)
            for _ in range(10):
                time.sleep(0.5)
                if self._is_chrome_cdp_active(port):
                    print(f"[+] Chrome debug port {port} is open and verified now.")
                    return True
                    
            print("[-] Timeout waiting for Chrome debug port to open.")
            return False
        except Exception as e:
            print(f"[-] Failed to launch Chrome: {e}")
            return False

    def _is_chrome_cdp_active(self, port: int) -> bool:
        import requests
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=0.5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        return False

    def check_and_launch_chrome(self, port: Optional[int] = None) -> bool:
        """
        Alias wrapper to keep compatibility with routes.py calling core.check_and_launch_chrome(port)
        """
        return self.ensure_chrome_debug_port(port)

    def check_login_status(self, port: Optional[int] = None) -> bool:
        return self.ensure_chrome_debug_port(port)

    def run_login_flow(self, port: Optional[int] = None) -> bool:
        # Just ensure the Chrome debug port is open. No extra browser is launched.
        return self.ensure_chrome_debug_port(port)
