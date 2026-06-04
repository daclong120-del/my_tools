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
    Lưu kết quả trích xuất YouTube vào file CSV.
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

def main():
    # Khởi tạo core (bỏ qua SQLite db init để kết nối nhanh chóng)
    core = SocialPetaDownloaderCore(skip_db_init=True)
    port = 9222
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "scraped_youtube_links.csv")
    
    print(f"[*] File CSV đầu ra: {csv_path}")
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
            results = core.youtube_service.click_and_extract_youtube_from_page(current_page)
            
            if not results:
                print("[-] Không tìm thấy hoặc không trích xuất được link YouTube nào từ trang hiện tại.")
            else:
                print(f"\n[🏁] Trích xuất thành công {len(results)} đường dẫn YouTube!")
                for idx, res in enumerate(results, 1):
                    print(f"  {idx}. ID: {res.get('ad_id')} | App: {res.get('app_name')} | URL: {res.get('youtube_url')}")
                
                # Lưu vào CSV
                print(f"[*] Đang lưu {len(results)} dòng dữ liệu vào file CSV...")
                save_to_csv(csv_path, results)
                print(f"[🎉] Đã lưu thành công dữ liệu vào: {csv_path}")
                
        except Exception as e:
            print(f"[-] Gặp lỗi khi thao tác trên tab: {e}")
        finally:
            browser.close()
            print("[*] Đã ngắt kết nối trình duyệt an toàn.")

if __name__ == "__main__":
    main()
