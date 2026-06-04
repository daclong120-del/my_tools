import os
import sys
import time
import psutil
import requests

# Add tools to path to allow import
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from socialpeta_downloader.core.chrome import ChromeService
from socialpeta_downloader.config import settings

def print_result(passed, text):
    if passed:
        print(f"✅ PASS - {text}")
    else:
        print(f"❌ FAIL - {text}")

def kill_processes_on_port(port):
    """Clean up any leftover Chrome instances on the test port."""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='tcp'):
                if conn.laddr.port == port or (conn.raddr and conn.raddr.port == port):
                    print(f"[*] Terminating process {proc.info['name']} (PID {proc.info['pid']}) on port {port}")
                    proc.terminate()
                    proc.wait(timeout=3)
        except (psutil.AccessDenied, psutil.NoSuchProcess, Exception):
            continue

def run_chrome_tests():
    TEST_PORT = 9333  # Use a custom port to avoid conflict with default 9222/8003
    print(f"=== Starting chrome.py verification tests on port {TEST_PORT} ===")
    
    # 1. Clean up any existing process on TEST_PORT
    kill_processes_on_port(TEST_PORT)
    time.sleep(1)
    
    service = ChromeService()
    
    # 2. Test _is_chrome_cdp_active when inactive
    is_active = service._is_chrome_cdp_active(TEST_PORT)
    print_result(not is_active, f"_is_chrome_cdp_active returns False when no Chrome is running on port {TEST_PORT}")
    
    # 3. Test ensure_chrome_debug_port (Launch new Chrome)
    success = service.ensure_chrome_debug_port(TEST_PORT)
    print_result(success, f"ensure_chrome_debug_port successfully launches Chrome on port {TEST_PORT}")
    
    # 4. Test _is_chrome_cdp_active when active
    is_active_now = service._is_chrome_cdp_active(TEST_PORT)
    print_result(is_active_now, f"_is_chrome_cdp_active returns True when Chrome is running on port {TEST_PORT}")
    
    # 5. Test check_and_launch_chrome (should reuse existing instance)
    success_reuse_1 = service.check_and_launch_chrome(TEST_PORT)
    print_result(success_reuse_1, "check_and_launch_chrome reuses existing active instance")
    
    # 6. Test check_login_status (should reuse existing instance)
    success_reuse_2 = service.check_login_status(TEST_PORT)
    print_result(success_reuse_2, "check_login_status reuses existing active instance")
    
    # 7. Test run_login_flow (should reuse existing instance)
    success_reuse_3 = service.run_login_flow(TEST_PORT)
    print_result(success_reuse_3, "run_login_flow reuses existing active instance")
    
    # 8. Clean up
    print("[*] Cleaning up Chrome process on test port...")
    kill_processes_on_port(TEST_PORT)
    
    is_active_after = service._is_chrome_cdp_active(TEST_PORT)
    print_result(not is_active_after, "Chrome successfully terminated and port is closed")

if __name__ == '__main__':
    run_chrome_tests()
