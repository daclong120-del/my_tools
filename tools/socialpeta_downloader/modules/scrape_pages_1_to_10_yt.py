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
from socialpeta_downloader.modules.page_navigation import navigate_to_page

def append_to_csv_report(filepath, rows):
    """
    Ghi thêm dòng dữ liệu vào file CSV kết quả.
    """
    fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                  "duration", "impression", "heat", "platform", "download_time",
                  "publisher", "app_name", "area", "copywriting_language", "title",
                  "body", "deployment_time", "saved_path", "file_size"]
    
    with open(filepath, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for row in rows:
            clean_row = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(clean_row)

def is_untruncated_youtube_url(url: str) -> bool:
    """
    Kiểm tra xem một đường dẫn YouTube có bị cắt cụt hay không (chứa ID video đầy đủ 11 ký tự).
    """
    if not url:
        return False
    # 1. watch?v=ID hoặc &v=ID
    match_v = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
    if match_v:
        vid = match_v.group(1)
        return len(vid) == 11
        
    # 2. youtu.be/ID
    match_short = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if match_short:
        vid = match_short.group(1)
        return len(vid) == 11

    # 3. embed/ID hoặc shorts/ID hoặc v/ID
    match_path = re.search(r'/(?:embed|shorts|v)/([a-zA-Z0-9_-]+)', url)
    if match_path:
        vid = match_path.group(1)
        return len(vid) == 11
        
    return False

def main():
    core = SocialPetaDownloaderCore()
    port = 9222
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "scraped_creatives_1_to_10.csv")
    
    fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                  "duration", "impression", "heat", "platform", "download_time",
                  "publisher", "app_name", "area", "copywriting_language", "title",
                  "body", "deployment_time", "saved_path", "file_size"]
                  
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
            print(f"[WARN] Không đọc được số trang hiện tại từ UI, mặc định coi là 1. Chi tiết: {e}")
            current_page = 1
            
        # Khởi tạo/ghi đè file CSV trống có tiêu đề
        with open(csv_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
        # Nếu đang ở trang 1, ta cần chuyển sang trang 2 trước để kích hoạt lại API khi quay về trang 1
        if current_page == 1:
            print("[*] Đang chuyển sang Trang 2 tạm thời để kích hoạt lại API khi quay về Trang 1...")
            success_temp = navigate_to_page(core, page, 2)
            if not success_temp:
                print("[-] Thất bại khi di chuyển sang trang tạm 2. Vẫn sẽ tiếp tục vòng lặp.")
            time.sleep(3.0)
            
        # Vòng lặp duyệt từ trang 1 đến trang 10
        for p_num in range(1, 11):
            print(f"\n[🚀] Bắt đầu cào dữ liệu cho Trang {p_num}/10...")
            
            try:
                # Bước 1: Lắng nghe phản hồi API và chuyển sang trang p_num
                print(f"[*] Đang điều hướng đến Trang {p_num} và chờ bắt gói tin API...")
                with page.expect_response(
                    lambda r: "/creative/list" in r.url or "/creative-rank/list" in r.url,
                    timeout=30000
                ) as response_info:
                    success_nav = navigate_to_page(core, page, p_num)
                    if not success_nav:
                        print(f"[-] Thất bại khi điều hướng đến Trang {p_num}.")
                        continue
                        
                response = response_info.value
                url = response.url
                print(f"[+] Đã nhận phản hồi từ API URL: {url}")
                
                # Đợi 1.5 giây để giao diện cập nhật trạng thái hoạt động trên UI
                time.sleep(1.5)
                
                # Bước 2: Kiểm tra xem đã thực sự ở đúng trang mục tiêu trên UI chưa
                actual_page = core.get_current_page(page)
                print(f"[*] Kiểm tra UI: Trang hiện tại hiển thị trên giao diện là {actual_page}")
                if actual_page != p_num:
                    print(f"[WARN] Cảnh báo: Giao diện hiển thị trang {actual_page} khác với mục tiêu {p_num}!")
                
                # Bước 3: Parse dữ liệu từ API
                body = response.json()
                raw_items = core.sniffer_service._recursive_find_creatives(body)
                parsed_items = []
                if raw_items:
                    print(f"[📡] Bắt được {len(raw_items)} quảng cáo thô từ API phản hồi của Trang {p_num}.")
                    for raw in raw_items:
                        parsed = core.utils_service._parse_creative_item(raw)
                        if parsed.get("ad_id"):
                            parsed_items.append(parsed)
                else:
                    print(f"[-] Không tìm thấy quảng cáo nào trong phản hồi API của Trang {p_num}.")
                    continue
                    
                # Bước 4: Kiểm tra xem có quảng cáo YouTube nào cần lấy link thực tế bằng click không
                has_youtube_to_scrape = False
                for item in parsed_items:
                    platform = item.get("platform", "").lower()
                    media_type = item.get("media_type", "")
                    yt_url = item.get("youtube_url", "")
                    
                    is_yt = (platform == "youtube" or media_type in ["youtube_video", "youtube_click_required"])
                    has_valid_yt = is_untruncated_youtube_url(yt_url)
                    if is_yt and not has_valid_yt:
                        has_youtube_to_scrape = True
                        break
                        
                # Bước 5: Thực hiện click chính xác các icon YouTube để lấy link thực tế (nếu cần)
                if has_youtube_to_scrape:
                    print(f"[*] Phát hiện quảng cáo YouTube cần lấy link trên Trang {p_num}. Bắt đầu quét và click...")
                    clicked_results = core.custom_click_and_extract_youtube_from_page(page)
                    
                    if clicked_results:
                        print(f"[+] Trích xuất được {len(clicked_results)} link YouTube từ thao tác click. Bắt đầu khớp nối...")
                        matched_count = 0
                        for clicked in clicked_results:
                            youtube_url = clicked.get("youtube_url")
                            clicked_ad_id = clicked.get("ad_id")
                            clicked_app_name = clicked.get("app_name") or ""
                            
                            if not youtube_url:
                                continue
                                
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
                                        print(f"    [✓] Khớp theo ID ({clicked_ad_id}): {youtube_url}")
                                        break
                                        
                            if matched:
                                continue
                                
                            # Khớp theo app_name gần đúng
                            res_app_clean = core.clean_app_name(clicked_app_name)
                            if res_app_clean:
                                for item in parsed_items:
                                    item_app_clean = core.clean_app_name(item.get("app_name", ""))
                                    if item_app_clean == res_app_clean:
                                        item_platform = item.get("platform", "").lower()
                                        item_media_type = item.get("media_type", "")
                                        is_item_yt = (item_platform == "youtube" or item_media_type in ["youtube_video", "youtube_click_required"])
                                        old_url = str(item.get("youtube_url", "")).strip()
                                        
                                        if is_item_yt and (not old_url or not is_untruncated_youtube_url(old_url)):
                                            item["youtube_url"] = youtube_url
                                            item["media_type"] = "youtube_video"
                                            item["platform"] = "youtube"
                                            matched = True
                                            matched_count += 1
                                            print(f"    [~] Khớp theo App ({clicked_app_name} -> {item.get('app_name')}): {youtube_url}")
                                            break
                                            
                        print(f"[+] Hoàn tất khớp nối! Đã khớp thành công {matched_count}/{len(clicked_results)} quảng cáo YouTube.")
                    else:
                        print("[-] Không click trích xuất được link YouTube nào trên giao diện.")
                else:
                    print("[*] Trang này không có quảng cáo YouTube nào cần lấy thêm link.")
                    
                # Bước 6: Lưu/Append dữ liệu trang này vào file CSV
                if parsed_items:
                    append_to_csv_report(csv_path, parsed_items)
                    print(f"[🏁] Đã lưu xong {len(parsed_items)} quảng cáo của Trang {p_num} vào: {csv_path}")
                
            except Exception as e:
                print(f"[-] Lỗi trong quá trình xử lý Trang {p_num}: {e}")
                
        browser.close()
        print(f"\n[🏁] Hoàn tất cào dữ liệu từ trang 1 đến 10. File báo cáo: {csv_path}")

if __name__ == "__main__":
    main()
