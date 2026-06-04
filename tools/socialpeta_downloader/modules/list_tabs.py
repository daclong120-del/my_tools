import os
import sys

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    port = 9222
    print(f"[*] Đang quét tìm các tab SocialPeta đang mở trên Chrome debug port {port}...")
    
    # Khởi tạo core và bỏ qua việc nạp DB SQLite để phản hồi ngay lập tức
    core = SocialPetaDownloaderCore(skip_db_init=True)
    
    if not core.chrome_service.ensure_chrome_debug_port(port):
        print(f"[-] LỖI: Không thể kết nối tới Chrome debug port {port}. Vui lòng đảm bảo Chrome được mở với --remote-debugging-port={port}.")
        return

    active_tabs = core.detect_tabs(port)
    if not active_tabs:
        print("[!] Không tìm thấy tab SocialPeta nào đang mở.")
        print("    Vui lòng mở SocialPeta trên Chrome (ví dụ: các trang tìm kiếm quảng cáo).")
        return
        
    print(f"[+] Tìm thấy {len(active_tabs)} tab SocialPeta đang hoạt động:")
    print("-" * 80)
    for tab in active_tabs:
        print(f"Index: {tab['index']}")
        print(f"Title: {tab['title']}")
        print(f"URL  : {tab['url']}")
        print(f"ID   : {tab['tab_id']}")
        print("-" * 80)

if __name__ == "__main__":
    main()
