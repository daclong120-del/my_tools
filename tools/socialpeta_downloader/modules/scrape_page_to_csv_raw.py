import os
import sys
import time
import csv
import re
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.test.page_navigation import navigate_to_page

def overwrite_raw_csv(filepath, rows):
    """
    Ghi đè lại file CSV thô với 20 cột tiêu chuẩn.
    """
    fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                  "duration", "impression", "heat", "platform", "download_time",
                  "publisher", "app_name", "area", "copywriting_language", "title",
                  "body", "deployment_time", "saved_path", "file_size"]
    
    with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            clean_row = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(clean_row)

def main():
    core = SocialPetaDownloaderCore()
    port = 9222
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "scraped_creatives_raw.csv")
    
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
                
            # Tiến hành cào
            body = response.json()
            raw_items = core.sniffer_service._recursive_find_creatives(body)
            if raw_items:
                print(f"[📡] Bắt được {len(raw_items)} quảng cáo của Trang gốc {current_page}.")
                parsed_items = []
                for raw in raw_items:
                    parsed = core.utils_service._parse_creative_item(raw)
                    if parsed.get("ad_id"):
                        parsed_items.append(parsed)
                
                # Kiểm tra xem có quảng cáo YouTube nào cần cào link hay không
                has_youtube_to_scrape = False
                for item in parsed_items:
                    platform = item.get("platform", "").lower()
                    media_type = item.get("media_type", "")
                    yt_url = item.get("youtube_url", "")
                    
                    is_yt = (platform == "youtube" or media_type in ["youtube_video", "youtube_click_required"])
                    has_valid_yt = ("youtube.com" in yt_url.lower() or "youtu.be" in yt_url.lower())
                    if is_yt and not has_valid_yt:
                        has_youtube_to_scrape = True
                        break
                
                # Nếu có quảng cáo YouTube chưa có link, cào bằng click
                if has_youtube_to_scrape:
                    print("[*] Phát hiện quảng cáo YouTube cần lấy link. Bắt đầu quét và click từng icon trên trang...")
                    results = core.custom_click_and_extract_youtube_from_page(page)
                    if results:
                        print(f"[*] Đang tiến hành khớp nối link YouTube vừa cào vào danh sách quảng cáo...")
                        for res in results:
                            res_ad_id = str(res.get("ad_id", "")).strip()
                            res_url = str(res.get("youtube_url", "")).strip()
                            if not res_ad_id or not res_url:
                                continue
                                
                            matched = False
                            # 1. So khớp chính xác theo ad_id
                            for item in parsed_items:
                                item_ad_id = str(item.get("ad_id", "")).strip()
                                if item_ad_id == res_ad_id:
                                    item["youtube_url"] = res_url
                                    if item.get("media_type") == "youtube_click_required":
                                        item["media_type"] = "youtube_video"
                                    matched = True
                                    print(f"  [✓] Cập nhật (khớp ID {res_ad_id}): {res_url}")
                                    break
                                    
                            # 2. Fuzzy fallback: So khớp theo app_name được làm sạch nếu không khớp ID
                            if not matched:
                                res_app_clean = core.clean_app_name(res.get("app_name", ""))
                                if res_app_clean:
                                    for item in parsed_items:
                                        item_app_clean = core.clean_app_name(item.get("app_name", ""))
                                        if item_app_clean == res_app_clean:
                                            item_platform = item.get("platform", "").lower()
                                            item_media_type = item.get("media_type", "")
                                            is_item_yt = (item_platform == "youtube" or item_media_type in ["youtube_video", "youtube_click_required"])
                                            old_url = str(item.get("youtube_url", "")).strip()
                                            
                                            if is_item_yt and (not old_url or not ("youtube.com" in old_url.lower() or "youtu.be" in old_url.lower())):
                                                item["youtube_url"] = res_url
                                                if item.get("media_type") == "youtube_click_required":
                                                    item["media_type"] = "youtube_video"
                                                matched = True
                                                print(f"  [~] Cập nhật (khớp App '{res_app_clean}', ID {item.get('ad_id')}): {res_url}")
                                                break
                    else:
                        print("[-] Không cào được link YouTube nào trên trang.")
                
                # Ghi đè lại file CSV thô với duy nhất danh sách quảng cáo của trang vừa cào
                overwrite_raw_csv(csv_path, parsed_items)
                print(f"[+] Đã ghi đè {len(parsed_items)} quảng cáo của trang hiện tại vào file CSV thô.")
            else:
                print("[-] Không tìm thấy quảng cáo nào trong phản hồi API.")
                
        except Exception as e:
            print(f"[-] Lỗi trong quá trình di chuyển trang hoặc xử lý phản hồi API: {e}")
            
        browser.close()
        print(f"\n[🏁] Hoàn tất cào trang {current_page}.")

if __name__ == "__main__":
    main()
