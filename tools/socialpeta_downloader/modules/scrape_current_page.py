import os
import sys
import time
import re
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.test.page_navigation import navigate_to_page

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
        try:
            current_page = core.get_current_page(page)
            print(f"[+] Bạn đang ở trang: {current_page}")
        except Exception as e:
            print(f"[-] Thất bại khi đọc trang hiện tại: {e}")
            browser.close()
            return
            
        # Quyết định trang tạm để nhảy qua để kích hoạt bắt gói tin API
        temp_page = 2 if current_page == 1 else current_page - 1
        print(f"[*] Trang tạm được chọn để chuyển đổi: Trang {temp_page}")
        
        parsed_items = []
        
        try:
            # Bước 1: Di chuyển tạm sang trang khác
            print(f"[*] Bước 1: Đang chuyển tạm sang Trang {temp_page}...")
            success_temp = navigate_to_page(core, page, temp_page)
            if not success_temp:
                print("[-] Thất bại khi di chuyển sang trang tạm.")
                browser.close()
                return
            
            # Đợi 1 chút để trang mới load ổn định
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
                
            # Đọc dữ liệu thô từ API phản hồi
            body = response.json()
            raw_items = core.sniffer_service._recursive_find_creatives(body)
            if raw_items:
                print(f"[📡] Bắt được {len(raw_items)} quảng cáo thô từ API phản hồi.")
                for raw in raw_items:
                    parsed = core.utils_service._parse_creative_item(raw)
                    parsed_items.append(parsed)
            else:
                print("[-] Không tìm thấy quảng cáo nào trong phản hồi API.")
                
            # Bước 4: Thực hiện click chính xác các icon YouTube để lấy link thực tế
            print("\n[*] Bước 4: Tiến hành quét và click các icon YouTube trên trang hiện tại...")
            clicked_results = core.youtube_service.click_and_extract_youtube_from_page(page)
            
            if clicked_results:
                print(f"[+] Trích xuất được {len(clicked_results)} link YouTube từ thao tác click.")
                
                # Bước 5: Khớp nối link YouTube đã click vào các entry tương ứng từ API
                print("[*] Bước 5: Khớp nối link YouTube với dữ liệu quảng cáo từ API...")
                matched_count = 0
                for clicked in clicked_results:
                    youtube_url = clicked.get("youtube_url")
                    clicked_ad_id = clicked.get("ad_id")
                    clicked_app_name = clicked.get("app_name") or ""
                    
                    matched = False
                    # Khớp theo ad_id
                    if clicked_ad_id:
                        for item in parsed_items:
                            if str(item.get("ad_id")) == str(clicked_ad_id):
                                item["youtube_url"] = youtube_url
                                item["media_type"] = "youtube_video"
                                item["platform"] = "youtube"
                                matched = True
                                matched_count += 1
                                print(f"    [+] Khớp theo ID ({clicked_ad_id}): {youtube_url}")
                                break
                    
                    if matched:
                        continue
                        
                    # Khớp theo app_name gần đúng
                    for item in parsed_items:
                        item_app_name = item.get("app_name") or ""
                        if clicked_app_name and item_app_name:
                            if clicked_app_name.lower() in item_app_name.lower() or item_app_name.lower() in clicked_app_name.lower():
                                item["youtube_url"] = youtube_url
                                item["media_type"] = "youtube_video"
                                item["platform"] = "youtube"
                                matched = True
                                matched_count += 1
                                print(f"    [+] Khớp theo App ({clicked_app_name} -> {item_app_name}): {youtube_url}")
                                break
                                
                    if not matched:
                        print(f"    [-] Không tìm thấy card phù hợp từ API cho click (App: {clicked_app_name}, URL: {youtube_url})")
                
                print(f"[+] Hoàn tất khớp nối! Khớp thành công {matched_count}/{len(clicked_results)} quảng cáo.")
            else:
                print("[-] Không tìm thấy hoặc không click trích xuất được link YouTube nào trên giao diện.")
                
            # Bước 6: Lưu tất cả dữ liệu (đã được cập nhật link YouTube) vào CSV
            if parsed_items:
                print(f"\n[*] Bước 6: Đang lưu {len(parsed_items)} quảng cáo vào file CSV...")
                for item in parsed_items:
                    core.append_to_custom_csv(csv_path, item)
                print(f"[🏁] Đã lưu thành công dữ liệu vào: {csv_path}")
            
        except Exception as e:
            print(f"[-] Lỗi trong quá trình thực thi: {e}")
            
        browser.close()
        print("\n[🏁] Hoàn tất toàn bộ chu trình cào dữ liệu.")

if __name__ == "__main__":
    main()
