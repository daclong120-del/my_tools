import os
import sys
from playwright.sync_api import sync_playwright

# Thêm đường dẫn thư mục chứa package "socialpeta_downloader" vào sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = current_dir
while parent_dir and os.path.basename(parent_dir) != "tools":
    new_parent = os.path.dirname(parent_dir)
    if new_parent == parent_dir:
        break
    parent_dir = new_parent
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.core.utils import is_socialpeta_url

def main():
    port = 9222
    # Khởi tạo core nhanh chóng bằng cách bỏ qua nạp DB SQLite
    core = SocialPetaDownloaderCore(skip_db_init=True)
    
    print(f"[*] Bước 1: Kiểm tra và đảm bảo cổng debug {port}...")
    if not core.chrome_service.ensure_chrome_debug_port(port):
        print(f"[-] LỖI: Không thể kết nối tới Chrome debug port {port}.")
        return

    print("[*] Bước 2: Kết nối CDP và tìm kiếm tab hiện tại đang active...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        except Exception as e:
            print(f"[-] LỖI: Không thể kết nối tới Chrome qua CDP: {e}")
            return
            
        context = browser.contexts[0]
        
        # Thao tác phụ để kích hoạt context (nếu cần)
        try:
            temp_page = context.new_page()
            temp_page.close()
        except Exception:
            pass
            
        current_page = None
        socialpeta_pages = []
        
        for page in context.pages:
            url = page.url
            if url and is_socialpeta_url(url):
                socialpeta_pages.append(page)
                try:
                    # Kiểm tra xem trang có đang hiển thị tích cực không
                    visibility = page.evaluate("document.visibilityState")
                    if visibility == "visible":
                        current_page = page
                        break
                except Exception:
                    pass
                    
        # Nếu không tìm thấy tab 'visible' (ví dụ trình duyệt đang bị thu nhỏ),
        # tự động lấy tab đầu tiên làm mặc định
        if not current_page and socialpeta_pages:
            print("[!] Không phát hiện tab đang hiển thị trực tiếp (có thể trình duyệt đang bị ẩn/minimized).")
            print("[*] Tự động chọn tab SocialPeta đầu tiên làm mặc định.")
            current_page = socialpeta_pages[0]
            
        if not current_page:
            print("[-] LỖI: Không tìm thấy tab SocialPeta nào đang mở.")
            browser.close()
            return
            
        try:
            current_title = current_page.title()
            current_url = current_page.url
            print("\n" + "="*80)
            print("[🎉] KẾT NỐI THÀNH CÔNG TỚI TAB HIỆN TẠI (CURRENT TAB):")
            print(f"    - Tiêu đề : {current_title}")
            print(f"    - URL      : {current_url}")
            print("="*80 + "\n")
            
            # Anh có thể thực hiện thêm các thao tác khác tại đây
            
        except Exception as e:
            print(f"[-] Có lỗi xảy ra khi giao tiếp với tab: {e}")
        finally:
            # Ngắt kết nối CDP an toàn
            browser.close()
            print("[*] Đã ngắt kết nối trình duyệt an toàn.")

if __name__ == "__main__":
    main()
