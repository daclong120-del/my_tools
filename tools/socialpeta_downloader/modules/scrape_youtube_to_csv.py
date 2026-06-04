import os
import sys
import time
import csv
from datetime import datetime
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.core.utils import is_socialpeta_url

def save_to_csv(filepath, results):
    """
    Lưu kết quả trích xuất YouTube vào file CSV. (Hành vi legacy dự phòng)
    Dùng encoding utf-8-sig để hiển thị tốt tiếng Việt/ký tự đặc biệt trên Excel của Windows.
    """
    file_exists = os.path.exists(filepath)
    fieldnames = ["ad_id", "app_name", "youtube_url", "title", "body", "scraped_time"]
    
    # Đảm bảo thư mục cha tồn tại
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(filepath, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            
        for item in results:
            row = {
                "ad_id": item.get("ad_id", ""),
                "app_name": item.get("app_name", ""),
                "youtube_url": item.get("youtube_url", ""),
                "title": item.get("title", ""),
                "body": item.get("body", ""),
                "scraped_time": now_str
            }
            writer.writerow(row)

def overwrite_raw_csv(filepath, rows):
    """
    Ghi đè lại file CSV thô với 20 cột tiêu chuẩn sau khi đã cập nhật youtube_url.
    """
    fieldnames = ["ad_id", "video_name", "media_type", "video_url", "youtube_url", "image_url",
                  "duration", "impression", "heat", "platform", "download_time",
                  "publisher", "app_name", "area", "copywriting_language", "title",
                  "body", "deployment_time", "saved_path", "file_size"]
    
    with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Đảm bảo chỉ ghi các cột hợp lệ
            clean_row = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(clean_row)

def main():
    # Khởi tạo core với skip_db_init=True để tránh khởi tạo db SQLite
    core = SocialPetaDownloaderCore(skip_db_init=True)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    raw_csv_path = os.path.join(script_dir, "scraped_creatives_raw.csv")
    
    # Kiểm tra xem có file raw CSV không
    has_raw_csv = os.path.exists(raw_csv_path)
    raw_creatives = []
    missing_youtube_count = 0
    
    if has_raw_csv:
        print(f"[+] Phát hiện file CSV thô: {raw_csv_path}")
        try:
            with open(raw_csv_path, mode="r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.DictReader(f)
                raw_creatives = list(reader)
                
            # Lọc đếm các quảng cáo YouTube bị thiếu youtube_url
            for row in raw_creatives:
                platform = row.get("platform", "").lower()
                media_type = row.get("media_type", "")
                yt_url = row.get("youtube_url", "")
                
                is_yt = (platform == "youtube" or media_type in ["youtube_video", "youtube_click_required"])
                has_valid_yt = ("youtube.com" in yt_url.lower() or "youtu.be" in yt_url.lower())
                
                if is_yt and not has_valid_yt:
                    missing_youtube_count += 1
            
            print(f"[*] Tìm thấy {len(raw_creatives)} dòng tổng cộng, trong đó có {missing_youtube_count} quảng cáo YouTube cần điền link.")
            
            if missing_youtube_count == 0:
                print("[+] Tất cả quảng cáo YouTube trong file raw CSV đã có link youtube_url đầy đủ. Không cần cào thêm.")
                # Vẫn tiếp tục chạy đề phòng người dùng muốn quét lại hoặc cào thêm ad mới xuất hiện trên UI
        except Exception as e:
            print(f"[-] Lỗi khi đọc file CSV thô: {e}")
            has_raw_csv = False

    port = 9222
    print(f"[*] Đang kết nối tới trình duyệt Chrome qua CDP cổng {port}...")
    
    # Đảm bảo port 9222 đang mở và đưa Chrome lên foreground
    if not core.chrome_service.ensure_chrome_debug_port(port):
        print(f"[-] LỖI: Không thể mở/kết nối tới Chrome debug port {port}.")
        return
        
    core.utils_service.bring_chrome_to_foreground()
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception as e:
            print(f"[-] LỖI: Không thể kết nối tới Chrome qua CDP: {e}")
            return
            
        context = browser.contexts[0]
        
        # Thao tác phụ để đồng bộ context
        try:
            temp_page = context.new_page()
            temp_page.close()
        except Exception:
            pass
            
        current_page = None
        socialpeta_pages = []
        
        # Tìm tab đang visible tích cực
        for page in context.pages:
            url = page.url
            if url and is_socialpeta_url(url):
                socialpeta_pages.append(page)
                try:
                    visibility = page.evaluate("document.visibilityState")
                    if visibility == "visible":
                        current_page = page
                        break
                except Exception:
                    pass
                    
        # Nếu không có tab nào visible (ví dụ Chrome đang thu nhỏ), chọn tab đầu tiên
        if not current_page and socialpeta_pages:
            print("[!] Không phát hiện tab đang hiển thị trực tiếp (Chrome đang bị thu nhỏ hoặc bị ẩn).")
            print("[*] Tự động kết nối tới tab SocialPeta đầu tiên.")
            current_page = socialpeta_pages[0]
            
        if not current_page:
            print("[-] LỖI: Không tìm thấy tab SocialPeta nào đang mở trên trình duyệt.")
            browser.close()
            return
            
        try:
            current_title = current_page.title()
            current_url = current_page.url
            print("\n" + "="*80)
            print("[🎉] KẾT NỐI THÀNH CÔNG TỚI TAB:")
            print(f"    - Tiêu đề : {current_title}")
            print(f"    - URL      : {current_url}")
            print("="*80 + "\n")
            
            # Mang trang lên front để thực thi click
            try:
                current_page.bring_to_front()
            except Exception:
                pass
                
            # Đọc vị trí trang hiện tại trên giao diện UI (nếu có)
            try:
                page_num = core.get_current_page(current_page)
                print(f"[+] Bạn đang ở trang thứ: {page_num}")
            except Exception as e:
                print(f"[*] Không đọc được trang hiện tại từ giao diện UI: {e}")
            
            print("[*] Bắt đầu quét và click từng icon YouTube trên trang để lấy link thực tế...")
            results = core.custom_click_and_extract_youtube_from_page(current_page)
            
            if not results:
                print("[-] Không tìm thấy hoặc không trích xuất được link YouTube nào từ trang hiện tại.")
            else:
                print(f"\n[🏁] Trích xuất thành công {len(results)} đường dẫn YouTube!")
                for idx, res in enumerate(results, 1):
                    print(f"  {idx}. ID: {res.get('ad_id')} | App: {res.get('app_name')} | URL: {res.get('youtube_url')}")
                
                if has_raw_csv and raw_creatives:
                    print(f"[*] Đang tiến hành khớp nối và tự điền link vào file CSV thô...")
                    updated_count = 0
                    
                    for res in results:
                        res_ad_id = str(res.get("ad_id", "")).strip()
                        res_url = str(res.get("youtube_url", "")).strip()
                        if not res_ad_id or not res_url:
                            continue
                            
                        matched = False
                        # 1. So khớp chính xác theo ad_id
                        for row in raw_creatives:
                            row_ad_id = str(row.get("ad_id", "")).strip()
                            if row_ad_id == res_ad_id:
                                old_url = str(row.get("youtube_url", "")).strip()
                                # Chỉ điền nếu url cũ trống hoặc không hợp lệ
                                if not old_url or not ("youtube.com" in old_url.lower() or "youtu.be" in old_url.lower()):
                                    row["youtube_url"] = res_url
                                    if row.get("media_type") == "youtube_click_required":
                                        row["media_type"] = "youtube_video"
                                    updated_count += 1
                                    matched = True
                                    print(f"  [✓] Cập nhật (khớp ID {res_ad_id}): {res_url}")
                                    break
                                    
                        # 2. Fuzzy fallback: So khớp theo app_name được làm sạch nếu không khớp ID
                        if not matched:
                            res_app_clean = core.clean_app_name(res.get("app_name", ""))
                            if res_app_clean:
                                for row in raw_creatives:
                                    row_app_clean = core.clean_app_name(row.get("app_name", ""))
                                    if row_app_clean == res_app_clean:
                                        row_platform = row.get("platform", "").lower()
                                        row_media_type = row.get("media_type", "")
                                        is_row_yt = (row_platform == "youtube" or row_media_type in ["youtube_video", "youtube_click_required"])
                                        old_url = str(row.get("youtube_url", "")).strip()
                                        
                                        if is_row_yt and (not old_url or not ("youtube.com" in old_url.lower() or "youtu.be" in old_url.lower())):
                                            row["youtube_url"] = res_url
                                            if row.get("media_type") == "youtube_click_required":
                                                row["media_type"] = "youtube_video"
                                            updated_count += 1
                                            matched = True
                                            print(f"  [~] Cập nhật (khớp App '{res_app_clean}', ID {row.get('ad_id')}): {res_url}")
                                            break
                                            
                    # Lưu lại file CSV thô sau khi update
                    overwrite_raw_csv(raw_csv_path, raw_creatives)
                    print(f"[🎉] Hoàn tất cập nhật file CSV thô. Đã tự điền thành công {updated_count} đường dẫn YouTube vào {raw_csv_path}")
                else:
                    # Chạy hành vi cũ: Lưu vào scraped_youtube_links.csv
                    legacy_csv_path = os.path.join(script_dir, "scraped_youtube_links.csv")
                    print(f"[*] Không có file raw CSV. Đang lưu {len(results)} dòng dữ liệu vào file legacy CSV...")
                    save_to_csv(legacy_csv_path, results)
                    print(f"[🎉] Đã lưu thành công dữ liệu vào: {legacy_csv_path}")
                
        except Exception as e:
            print(f"[-] Gặp lỗi khi thao tác trên tab: {e}")
        finally:
            browser.close()
            print("[*] Đã ngắt kết nối trình duyệt an toàn.")

if __name__ == "__main__":
    main()
