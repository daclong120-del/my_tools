import os
import sys
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore()
    port = 9222
    
    with sync_playwright() as p:
        print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
        browser, page = core.connect_to_active_tab(p, port)
        if not page:
            print("[-] Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được.")
            return
            
        print("[*] Đang đọc vị trí trang hiện tại từ giao diện UI...")
        current_page = core.get_current_page(page)
        print(f"\n[🚀] BẠN ĐANG Ở TRANG: {current_page}\n")
        
        browser.close()

if __name__ == "__main__":
    main()

