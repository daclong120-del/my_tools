import os
import sys
import time
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.scripts.page_navigation import navigate_to_page

def main():
    core = SocialPetaDownloaderCore()
    port = 9222
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "scraped_creatives.csv")
    
    print(f"[*] File CSV đầu ra: {csv_path}")
    print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
    
    with sync_playwright() as p:
        browser, page = core.connect_to_active_tab(p, port)
        if not page:
            print("[-] Không tìm thấy tab SocialPeta đang hoạt động hoặc không kết nối được.")
            return
            
        print("[*] Đang đọc vị trí trang hiện tại từ giao diện UI...")
        current_page = core.get_current_page(page)
        print(f"[+] Bạn đang ở trang: {current_page}")
        
        # Quyết định trang tạm để nhảy qua
        temp_page = 2 if current_page == 1 else current_page - 1
        print(f"[*] Trang tạm được chọn để chuyển đổi: Trang {temp_page}")
        
        scraped_ids = set()
        
        try:
            # Bước 1: Di chuyển tạm sang trang khác
            print(f"[*] Bước 1: Đang chuyển tạm sang Trang {temp_page}...")
            success_temp = navigate_to_page(core, page, temp_page)
            if not success_temp:
                print("[-] Thất bại khi di chuyển sang trang tạm.")
                browser.close()
                return
            
            # Đợi 1 chút để chuyển trang hoàn tất ổn định
            time.sleep(2.0)
            
            # Bước 2: Lắng nghe phản hồi API và quay trở lại trang gốc (current_page)
            print(f"[*] Bước 2: Quay lại Trang gốc {current_page} và bắt gói tin API...")
            with page.expect_response(lambda r: "/creative/list" in r.url or "/creative-rank/list" in r.url, timeout=20000) as response_info:
                success_back = navigate_to_page(core, page, current_page)
                if not success_back:
                    print("[-] Thất bại khi quay lại trang gốc.")
                    browser.close()
                    return
            
            response = response_info.value
            url = response.url
            print(f"[+] Đã nhận phản hồi từ API URL: {url}")
            
            # Đợi 1.5 giây để giao diện cập nhật trạng thái hoạt động trên UI
            time.sleep(1.5)
            
            # Bước 3: Kiểm tra xem đã thực sự quay lại đúng trang gốc chưa
            actual_page = core.get_current_page(page)
            print(f"[*] Kiểm tra UI: Trang hiện tại hiển thị trên giao diện là {actual_page}")
            if actual_page != current_page:
                print(f"[-] Lỗi: Giao diện UI chưa quay về trang gốc ({current_page}) mà đang ở {actual_page}. Dừng cào dữ liệu.")
                browser.close()
                return
                
            # Tiến hành cào và lưu vào file CSV
            body = response.json()
            raw_items = core.sniffer_service._recursive_find_creatives(body)
            if raw_items:
                print(f"[📡] Bắt được {len(raw_items)} quảng cáo của Trang gốc {current_page}.")
                for raw in raw_items:
                    parsed = core.utils_service._parse_creative_item(raw)
                    ad_id = parsed.get("ad_id")
                    if ad_id and ad_id not in scraped_ids:
                        scraped_ids.add(ad_id)
                        core.append_to_custom_csv(csv_path, parsed)
                        print(f"    [+] Đã lưu quảng cáo vào CSV: {ad_id} - {parsed.get('app_name')}")
            else:
                print("[-] Không tìm thấy quảng cáo nào trong phản hồi API.")
                
        except Exception as e:
            print(f"[-] Lỗi trong quá trình di chuyển trang hoặc xử lý phản hồi API: {e}")
            
        browser.close()
        print(f"\n[🏁] Hoàn tất. Đã cào và lưu tổng cộng {len(scraped_ids)} quảng cáo mới vào CSV.")

if __name__ == "__main__":
    main()

