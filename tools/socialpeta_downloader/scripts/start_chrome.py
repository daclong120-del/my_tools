import os
import sys

# Thêm workspace root vào sys.path để import được socialpeta_downloader
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core.chrome import ChromeService

def main():
    print("[*] Đang khởi động Google Chrome với cổng debug 9222...")
    chrome_service = ChromeService()
    success = chrome_service.ensure_chrome_debug_port(9222)
    if success:
        print("[+] Khởi động Chrome debug thành công trên cổng 9222.")
    else:
        print("[-] Khởi động Chrome debug thất bại.")

if __name__ == "__main__":
    main()
