import os
import sys
import argparse

# Thêm đường dẫn thư mục gốc của project vào sys.path để import được core
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(parent_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore

def main():
    parser = argparse.ArgumentParser(description="Dọn dẹp phiên tải (SQLite, Cache JSON tạm thời và phân đoạn video tải tạm)")
    parser.add_argument(
        "--keep-history", "-k",
        action="store_true",
        help="Giữ lại lịch sử file CSV (download_info.csv) và bảng download_history trong SQLite"
    )
    args = parser.parse_args()
    
    print("[*] Khởi tạo Core...")
    core = SocialPetaDownloaderCore()
    
    clear_history = not args.keep_history
    if clear_history:
        print("[!] CẢNH BÁO: Tiến hành dọn dẹp TOÀN BỘ (xóa trắng lịch sử tải và tệp rác)...")
    else:
        print("[*] Chỉ dọn dẹp các tệp tạm thời và hàng đợi cache (vẫn GIỮ LẠI danh sách tệp tải thành công)...")
        
    try:
        core.clear_session_data(clear_history=clear_history)
        print("[+] Hoàn tất quá trình dọn dẹp phiên thành công!")
    except Exception as e:
        import traceback
        print(f"[-] Có lỗi xảy ra trong quá trình dọn dẹp: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
