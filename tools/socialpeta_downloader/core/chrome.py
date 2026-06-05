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
from socialpeta_downloader.core.protocols import IEngineContext

class ChromeService:
    def __init__(self, context: Optional[IEngineContext] = None):
        self.context = context

    # hàm đã hoạt động rồi đừng động vào
    def ensure_chrome_debug_port(self, port: Optional[int] = None, profile_dir: Optional[str] = None) -> bool:
        """
        Kiểm tra xem cổng debug đã được mở chưa. Nếu chưa, thử khởi chạy một trình duyệt
        Google Chrome cục bộ với chế độ Remote Debugging port và cấu hình profile riêng biệt.
        """
        port = port if port is not None else settings.CHROME_DEBUG_PORT
            
        if self._is_chrome_cdp_active(port):
            print(f"[+] Chrome debug port {port} is already active. Reusing existing instance.")
            print(f"[!] NOTE: If the crawler hangs or fails to download, please close all Chrome processes and run the tool again to let it launch Chrome with optimized background flags.")
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
        if profile_dir:
            chrome_profile_dir = profile_dir
        elif port == 9222:
            chrome_profile_dir = os.path.join(settings.DATA_DIR, "chrome_debug_profile")
        else:
            chrome_profile_dir = os.path.join(settings.DATA_DIR, f"chrome_debug_profile_{port}")
        os.makedirs(chrome_profile_dir, exist_ok=True)
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
            if self.context:
                import traceback
                self.context.log("error", f"[-] Failed to launch Chrome: {e}\n{traceback.format_exc()}")
            else:
                import traceback
                print(f"[-] Failed to launch Chrome: {e}\n{traceback.format_exc()}")
            return False

    # hàm đã hoạt động rồi đừng động vào
    def _is_chrome_cdp_active(self, port: int) -> bool:
        """
        Kiểm tra xem cổng debug CDP của Chrome đã hoạt động hay chưa bằng cách gửi
        yêu cầu HTTP GET tới endpoint cục bộ /json/version.
        """
        import requests
        try:
            resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=2.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        return False

    # hàm đã hoạt động rồi đừng động vào
    def check_and_launch_chrome(self, port: Optional[int] = None) -> bool:
        """
        Tên bí danh (alias wrapper) để tương thích với các tệp tin bên ngoài (như routes.py)
        khi gọi phương thức khởi chạy Chrome debug port.
        """
        return self.ensure_chrome_debug_port(port)

    # hàm đã hoạt động rồi đừng động vào
    def check_login_status(self, port: Optional[int] = None) -> bool:
        """
        Kiểm tra trạng thái đăng nhập bằng cách đảm bảo cổng debug Chrome đang mở.
        """
        return self.ensure_chrome_debug_port(port)

    # hàm đã hoạt động rồi đừng động vào
    def run_login_flow(self, port: Optional[int] = None) -> bool:
        """
        Khởi chạy tiến trình đăng nhập bằng cách đảm bảo cổng debug Chrome đã được mở sẵn.
        Không khởi chạy thêm cửa sổ phụ nào.
        """
        return self.ensure_chrome_debug_port(port)

    def run_start_chrome_cli(self, argv: Optional[list] = None) -> None:
        """
        Giao diện dòng lệnh (CLI) để khởi động Google Chrome với cổng debug 9222.
        """
        print("[*] Đang khởi động Google Chrome với cổng debug 9222...")
        success = self.ensure_chrome_debug_port(9222)
        if success:
            print("[+] Khởi động Chrome debug thành công trên cổng 9222.")
        else:
            print("[-] Khởi động Chrome debug thất bại.")

