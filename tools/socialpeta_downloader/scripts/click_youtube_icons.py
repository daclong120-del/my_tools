import os
import sys
import time
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    core = SocialPetaDownloaderCore()
    port = 9222
    
    print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
    
    with sync_playwright() as p:
        browser, page = core.connect_to_active_tab(p, port)
        if not page:
            print("[-] Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được.")
            return
            
        print("[*] Đang đọc vị trí trang hiện tại từ giao diện UI...")
        try:
            current_page = core.get_current_page(page)
            print(f"[+] Bạn đang ở trang: {current_page}")
        except Exception as e:
            print(f"[*] Không đọc được trang hiện tại: {e}")
        
        print("[*] Bắt đầu quét và click từng icon YouTube trên trang hiện tại để trích xuất link...")
        results = core.youtube_service.click_and_extract_youtube_from_page(page)
        
        if not results:
            print("[-] Không tìm thấy hoặc không trích xuất được link YouTube nào trên trang này.")
            browser.close()
            return
            
        print(f"\n[🏁] Hoàn tất! Trích xuất được {len(results)} đường dẫn YouTube:")
        
        for idx, res in enumerate(results, 1):
            youtube_url = res.get("youtube_url")
            ad_id = res.get("ad_id")
            app_name = res.get("app_name")
            title = res.get("title")
            body = res.get("body")
            
            print(f"  {idx}. ID: {ad_id} | App: {app_name} | URL: {youtube_url}")
            
        browser.close()
        print(f"\n[🏁] Xử lý xong {len(results)} quảng cáo YouTube trên trang.")

if __name__ == "__main__":
    main()
