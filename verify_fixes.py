import os
import sys
import time
import requests
import psutil

def print_result(passed, text):
    if passed:
        print(f"✅ PASS - {text}")
    else:
        print(f"❌ FAIL - {text}")

def count_cdp_connections():
    count = 0
    # Try global connections first
    try:
        for conn in psutil.net_connections(kind='tcp'):
            raddr = conn.raddr
            laddr = conn.laddr
            if (raddr and raddr.port == 9222) or (laddr and laddr.port == 9222):
                if conn.status != 'TIME_WAIT':
                    count += 1
        return count
    except Exception:
        pass
    
    # Fallback: process-specific connections
    count = 0
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name and name.lower() in ['api.exe', 'python.exe', 'pythonw.exe', 'chrome.exe']:
                for conn in proc.connections(kind='tcp'):
                    raddr = conn.raddr
                    laddr = conn.laddr
                    if (raddr and raddr.port == 9222) or (laddr and laddr.port == 9222):
                        if conn.status != 'TIME_WAIT':
                            count += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return count

def find_api_process():
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            if name and name.lower() == 'api.exe':
                return proc
            # Fallback for dev mode
            if name and name.lower() in ['python.exe', 'pythonw.exe']:
                cmdline = proc.info['cmdline']
                if cmdline:
                    cmdline_str = " ".join(cmdline)
                    if "socialpeta_downloader.api" in cmdline_str or ("uvicorn" in cmdline_str and "8003" in cmdline_str) or "api.py" in cmdline_str:
                        return proc
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return None

def run_tests():
    # -------------------------------------------------------------
    # TEST 1 - CORS
    # -------------------------------------------------------------
    try:
        headers = {"Origin": "https://google.com"}
        response = requests.get("http://127.0.0.1:8003/api/v1/socialpeta/status", headers=headers, timeout=5)
        allow_origin = response.headers.get("Access-Control-Allow-Origin")
        
        # Pass if returns 400 or the ACAO header is missing
        if response.status_code == 400 or not allow_origin:
            print_result(True, "Fix #1 CORS")
        else:
            print_result(False, f"Fix #1 CORS: API returned status {response.status_code} with Access-Control-Allow-Origin: {allow_origin}")
    except requests.exceptions.RequestException as e:
        print_result(False, f"Fix #1 CORS: Cannot connect to API server at http://127.0.0.1:8003 ({e})")

    # -------------------------------------------------------------
    # TEST 2 - CDP Leak
    # -------------------------------------------------------------
    try:
        # Measure initial connections
        conn_before = count_cdp_connections()
        
        # Trigger /tabs multiple times
        conns = [conn_before]
        for i in range(3):
            requests.get("http://127.0.0.1:8003/api/v1/socialpeta/tabs?port=9222", timeout=5)
            time.sleep(0.5)
            conns.append(count_cdp_connections())
            
        conn_after = conns[-1]
        
        # PASS if conn_after <= conn_before + 1
        if conn_after <= conn_before + 1:
            print_result(True, "Fix #2 CDP Leak")
        else:
            print_result(False, f"Fix #2 CDP Leak: Connections to port 9222 increased from {conn_before} to {conn_after} (history: {conns})")
    except Exception as e:
        print_result(False, f"Fix #2 CDP Leak: Error running test ({e})")

    # -------------------------------------------------------------
    # TEST 3 - Disk I/O
    # -------------------------------------------------------------
    proc = find_api_process()
    if proc is None:
        print_result(False, "Fix #3 Disk I/O: Process api.exe (or python dev api process) is not running")
    else:
        try:
            # Measure initial disk read bytes
            io_before = proc.io_counters().read_bytes
            time.sleep(5)
            io_after = proc.io_counters().read_bytes
            
            read_diff = io_after - io_before
            read_diff_mb = read_diff / (1024 * 1024)
            
            if read_diff_mb < 1.0:
                print_result(True, "Fix #3 Disk I/O")
            else:
                print_result(False, f"Fix #3 Disk I/O: High disk I/O detected, read {read_diff_mb:.2f} MB in 5 seconds (> 1MB)")
        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            print_result(False, f"Fix #3 Disk I/O: Permissions error or process terminated during test ({e})")

    # -------------------------------------------------------------
    # TEST 4 - Build
    # -------------------------------------------------------------
    root_dir = os.path.dirname(os.path.abspath(__file__))
    api_path = os.path.join(root_dir, "dist", "api.exe")
    
    if not os.path.exists(api_path):
        print_result(False, f"Fix #4 Build: dist/api.exe does not exist at {api_path}")
    else:
        size_bytes = os.path.getsize(api_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > 50.0:
            print_result(True, "Fix #4 Build")
        else:
            print_result(False, f"Fix #4 Build: File dist/api.exe size is {size_mb:.2f} MB (<= 50MB, likely missing Playwright collect-all)")

    # -------------------------------------------------------------
    # TEST 5 - CPU Spike / Stats keys
    # -------------------------------------------------------------
    try:
        response = requests.get("http://127.0.0.1:8003/api/v1/socialpeta/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            stats_dict = data.get("stats", {})
            if "pending" in stats_dict and "downloading" in stats_dict:
                print_result(True, "Fix #5 CPU Spike Stats Keys")
            else:
                print_result(False, f"Fix #5: 'pending' or 'downloading' keys missing in stats: {stats_dict}")
        else:
            print_result(False, f"Fix #5: API returned status {response.status_code}")
    except Exception as e:
        print_result(False, f"Fix #5: Cannot connect to stats API ({e})")

    # -------------------------------------------------------------
    # TEST 7 - WebSocket Multi-Client Broadcast
    # -------------------------------------------------------------
    try:
        routes_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "socialpeta_downloader", "api", "routes.py")
        with open(routes_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "active_connections" in content or "connections" in content:
            # Check if it broadcasts to all connections in a loop
            if "for connection in" in content or "for conn in" in content or "for ws in" in content:
                print_result(True, "Fix #7 WebSocket Multi-Client Broadcast")
            else:
                print_result(False, "Fix #7: Found connection list but no broadcast loop detected in routes.py")
        else:
            print_result(False, "Fix #7: Active connections list/set not found in routes.py")
    except Exception as e:
        print_result(False, f"Fix #7: Error checking routes.py ({e})")

    # -------------------------------------------------------------
    # TEST 9 - Silent Downloader Failures
    # -------------------------------------------------------------
    try:
        downloader_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "socialpeta_downloader", "core", "downloader.py")
        with open(downloader_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Should use self.log("error", ...) instead of print("[-] Loi tai/di chuyen...")
        unlogged_pattern_1 = 'print(f"[-] Loi di chuyen file anh:'
        unlogged_pattern_2 = 'print(f"[-] Loi tai video'
        unlogged_pattern_3 = 'print(f"[-] Loi in worker for'
        if unlogged_pattern_1 not in content and unlogged_pattern_2 not in content and unlogged_pattern_3 not in content:
            print_result(True, "Fix #9 Silent Downloader Failures")
        else:
            print_result(False, "Fix #9: Found unlogged print statements in downloader.py")
    except Exception as e:
        print_result(False, f"Fix #9: Error checking downloader.py ({e})")

if __name__ == '__main__':
    run_tests()
