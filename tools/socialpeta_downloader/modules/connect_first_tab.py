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

def main():
    port = 9222
    # Khởi tạo core nhanh chóng bằng cách bỏ qua nạp DB SQLite
    core = SocialPetaDownloaderCore(skip_db_init=True)
    
    print(f"[*] Bước 1: Kiểm tra và đảm bảo cổng debug {port}...")
    if not core.chrome_service.ensure_chrome_debug_port(port):
        print(f"[-] LỖI: Không thể kết nối tới Chrome debug port {port}.")
        return

    print("[*] Bước 2: Quét tìm các tab SocialPeta đang hoạt động...")
    active_tabs = core.detect_tabs(port)
    if not active_tabs:
        print("[-] LỖI: Không tìm thấy tab SocialPeta nào đang mở trên trình duyệt.")
        print("    Vui lòng mở SocialPeta (ví dụ: trang tìm kiếm quảng cáo) trước.")
        return
    
    first_tab = active_tabs[0]
    print(f"[+] Tìm thấy tab mục tiêu: Index {first_tab['index']} - Tiêu đề: {first_tab['title']}")
    
    print("[*] Bước 3: Đang kết nối Playwright CDP vào tab đầu tiên...")
    with sync_playwright() as p:
        browser, page = core.connect_to_active_tab(p, port)
        if not page:
            print("[-] LỖI: Không thể liên kết hoặc kết nối CDP tới tab hoạt động.")
            return
            
        try:
            # Lấy thông tin tiêu đề và URL thực tế từ tab để kiểm chứng
            current_title = page.title()
            current_url = page.url
            print("\n" + "="*80)
            print("[🎉] KẾT NỐI THÀNH CÔNG TỚI TAB:")
            print(f"    - Tiêu đề hiện tại : {current_title}")
            print(f"    - URL hiện tại      : {current_url}")
            print("="*80 + "\n")
            
            # Anh có thể thực hiện thêm các thao tác khác tại đây (ví dụ: page.click, page.fill, v.v...)
            
        except Exception as e:
            print(f"[-] Có lỗi xảy ra khi giao tiếp với tab: {e}")
        finally:
            print("[*] Đã nối trình duyệt an toàn.")

if __name__ == "__main__":
    main()
