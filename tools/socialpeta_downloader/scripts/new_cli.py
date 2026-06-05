# tools/socialpeta_downloader/scripts/new_cli.py
"""
Unified CLI Tool for SocialPeta Downloader.
Covers all commands: start-chrome, list-tabs, connect-tab, scrape, download, fill-names, crawl, clear.
"""

import sys
import os
import argparse
import time
import threading

# Set encoding on Windows to prevent UnicodeEncodeError
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='backslashreplace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='backslashreplace')

# Thêm workspace root/tools vào sys.path để import được socialpeta_downloader
scripts_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.dirname(os.path.dirname(scripts_dir))
if tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

from socialpeta_downloader.core import SocialPetaDownloaderCore
from socialpeta_downloader.core.chrome import ChromeService
from socialpeta_downloader.config import settings

def handle_start_chrome(args):
    print(f"[*] Khởi chạy Chrome debug với cổng: {args.port}...")
    chrome_service = ChromeService(context=None)
    success = chrome_service.ensure_chrome_debug_port(port=args.port, profile_dir=args.profile_dir)
    if success:
        print("[+] Chrome debug đã sẵn sàng.")
    else:
        print("[-] Không thể khởi chạy Chrome debug.")

def handle_list_tabs(args):
    core = SocialPetaDownloaderCore(skip_db_init=True)
    core.tab_scanner.run_list_tabs_cli(port=args.port)

def handle_connect_tab(args):
    core = SocialPetaDownloaderCore(skip_db_init=True)
    if args.mode == "current":
        core.tab_scanner.run_connect_current_tab_cli(port=args.port)
    elif args.mode == "first":
        core.tab_scanner.run_connect_first_tab_cli(port=args.port)

def handle_scrape(args):
    core = SocialPetaDownloaderCore()
    csv_path = args.csv_path
    
    if args.mode == "all":
        print(f"[*] Chế độ cào: all (tất cả quảng cáo trên trang hiện tại)...")
        core.sniffer_service.run_scrape_current_page_cli(csv_path=csv_path, port=args.port)
    elif args.mode == "youtube":
        print(f"[*] Chế độ cào: youtube (chỉ cào video YouTube)...")
        if args.pages <= 1:
            print(f"[*] Đang cào trang hiện tại...")
            core.youtube_service.run_scrape_current_page_yt_cli(csv_path=csv_path, port=args.port)
        else:
            print(f"[*] Đang cào {args.pages} trang...")
            core.youtube_service.run_scrape_pages_yt_cli(start_page=1, end_page=args.pages, csv_path=csv_path, port=args.port)

def handle_download(args):
    core = SocialPetaDownloaderCore(skip_db_init=True)
    csv_path = args.csv_path
    output_dir = args.output_dir
    threads = args.threads
    mode = args.mode

    if not os.path.exists(csv_path):
        print(f"[-] LỖI: File CSV không tồn tại tại: {csv_path}")
        sys.exit(1)

    print(f"[*] Bắt đầu tiến trình tải tài nguyên từ CSV: {csv_path}")
    print(f"[*] Chế độ tải: {mode} | Luồng tối đa: {threads}")
    if output_dir:
        print(f"[*] Thư mục lưu: {output_dir}")

    # Chạy lần lượt các tiến trình tải tùy theo chế độ lọc
    if mode in ("all", "image"):
        print("[*] Đang tải hình ảnh...")
        core.downloader_service.run_download_images_cli(csv_path=csv_path, output_dir=output_dir, max_workers=threads)

    if mode in ("all", "cdn-video"):
        print("[*] Đang tải video CDN trực tiếp...")
        core.downloader_service.run_download_videos_not_youtube_cli(csv_path=csv_path, output_dir=output_dir, max_workers=threads)

    if mode in ("all", "youtube"):
        print("[*] Đang tải video YouTube...")
        core.youtube_service.run_download_video_youtube_only_cli(csv_path=csv_path, output_dir=output_dir, max_workers=threads)

    print("[+] Hoàn tất tiến trình tải tài nguyên.")

def handle_fill_names(args):
    core = SocialPetaDownloaderCore(skip_db_init=True)
    csv_path = args.csv_path
    if not os.path.exists(csv_path):
        print(f"[-] LỖI: File CSV không tồn tại tại: {csv_path}")
        sys.exit(1)
        
    print(f"[*] Đang điền tên file thiếu cho CSV: {csv_path}...")
    filled = core.fill_video_names_in_csv(csv_path)
    print(f"[+] Hoàn tất! Đã điền {filled} tên file.")

def handle_crawl(args):
    core = SocialPetaDownloaderCore()
    if args.dir:
        core.update_download_dir(args.dir)
        
    pages_to_scrape = args.pages
    thread_count = args.threads

    print(f"[*] Khởi chạy SocialPeta Downloader Core với {thread_count} luồng...")
    core.start_system(thread_count=thread_count)
    
    print("[*] Đang quét các tab đang hoạt động trong Chrome...")
    active_tabs = core.detect_tabs()
    if not active_tabs:
        print("[-] Không tìm thấy tab SocialPeta nào. Vui lòng kiểm tra lại Chrome.")
        core.stop_system()
        sys.exit(1)
        
    threads = []
    for tab in active_tabs:
        idx = tab["index"]
        print(f"[*] Bắt đầu cào tab [{idx}] - {pages_to_scrape} trang...")
        t = threading.Thread(target=core.run_tab_scraper, args=(idx, pages_to_scrape), daemon=True)
        t.start()
        threads.append(t)
        
    try:
        while core.running:
            # Xóa màn hình nếu là terminal tty
            if sys.stdout.isatty():
                os.system('cls' if os.name == 'nt' else 'clear')
            print("==================================================")
            print("         STATUS MONITOR (NON-INTERACTIVE)         ")
            print("==================================================")
            
            scrapers_alive = any(t.is_alive() for t in threads)
            pending = core.stats.get("pending", 0)
            downloading = core.stats.get("downloading", 0)
            stats = core.stats
            
            print(f"  - Scrapers running: {scrapers_alive}")
            print(f"  - Total sniffed:    {stats.get('total_sniffed', 0)}")
            print(f"  - Waiting:          {pending}")
            print(f"  - Downloading:      {downloading}")
            print(f"  - Saved (Unique):   {stats.get('done', 0)}")
            print(f"  - Failed:           {stats.get('failed', 0)}")
            print(f"  - Expired:          {stats.get('expired', 0)}")
            print(f"  - Duplicate:        {stats.get('duplicate', 0)}")
            print("==================================================")
            
            if not scrapers_alive and pending == 0 and downloading == 0:
                print("[+] Tất cả luồng scraper đã hoàn thành va file đã tải xong!")
                break
                
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("[*] Người dùng yêu cầu dừng...")
    finally:
        print("[*] Đang dừng SocialPeta Downloader Engine...")
        core.stop_system()
        print("[+] Đã dừng SocialPeta Downloader.")

def handle_clear(args):
    core = SocialPetaDownloaderCore(skip_db_init=True)
    # run_clear_session_cli parses sys.argv by default, but we can pass custom argv to it
    argv = ["--keep-history"] if args.keep_history else []
    core.session_service.run_clear_session_cli(argv=argv)

def main():
    parser = argparse.ArgumentParser(description="Unified CLI Tool for SocialPeta Downloader API")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Các subcommand khả dụng")

    # start-chrome
    parser_start = subparsers.add_parser("start-chrome", help="Khởi động Google Chrome debug mode")
    parser_start.add_argument("--port", "-p", type=int, default=9222, help="Cổng debug của Chrome (mặc định: 9222)")
    parser_start.add_argument("--profile-dir", type=str, default=None, help="Đường dẫn thư mục profile Chrome")

    # list-tabs
    parser_list = subparsers.add_parser("list-tabs", help="Liệt kê danh sách tab SocialPeta đang hoạt động")
    parser_list.add_argument("--port", "-p", type=int, default=9222, help="Cổng debug của Chrome (mặc định: 9222)")

    # connect-tab
    parser_connect = subparsers.add_parser("connect-tab", help="Kiểm tra kết nối CDP tới tab SocialPeta")
    parser_connect.add_argument("--port", "-p", type=int, default=9222, help="Cổng debug của Chrome (mặc định: 9222)")
    parser_connect.add_argument("--mode", choices=["current", "first"], default="current", help="Tab chọn (mặc định: current)")

    # scrape
    parser_scrape = subparsers.add_parser("scrape", help="Cào dữ liệu trang hiện tại và lưu vào CSV")
    parser_scrape.add_argument("--port", "-p", type=int, default=9222, help="Cổng debug của Chrome (mặc định: 9222)")
    parser_scrape.add_argument("--pages", "-n", type=int, default=1, help="Số trang muốn cào (chỉ áp dụng cho youtube, mặc định: 1)")
    parser_scrape.add_argument("--mode", choices=["all", "youtube"], default="all", help="Chế độ cào (mặc định: all)")
    parser_scrape.add_argument("--csv-path", type=str, default=None, help="Đường dẫn lưu file CSV")

    # download
    parser_download = subparsers.add_parser("download", help="Tải tài nguyên hình ảnh / video từ file CSV")
    parser_download.add_argument("--csv-path", type=str, required=True, help="Đường dẫn tới file CSV chứa thông tin tải")
    parser_download.add_argument("--output-dir", type=str, default=None, help="Thư mục lưu tài nguyên tải về")
    parser_download.add_argument("--mode", choices=["all", "image", "youtube", "cdn-video"], default="all", help="Bộ lọc tải (mặc định: all)")
    parser_download.add_argument("--threads", "-t", type=int, default=3, help="Số luồng tải song song (mặc định: 3)")

    # fill-names
    parser_fill = subparsers.add_parser("fill-names", help="Điền tên file còn thiếu trong file CSV")
    parser_fill.add_argument("--csv-path", type=str, required=True, help="Đường dẫn tới file CSV cần cập nhật")

    # crawl
    parser_crawl = subparsers.add_parser("crawl", help="Chạy luồng cào và tải tự động hoàn toàn (Full Flow)")
    parser_crawl.add_argument("--pages", "-n", type=int, default=10, help="Số lượng trang muốn cào trên mỗi tab (mặc định: 10)")
    parser_crawl.add_argument("--threads", "-t", type=int, default=5, help="Số luồng tải song song (mặc định: 5)")
    parser_crawl.add_argument("--dir", "-d", type=str, default=None, help="Thư mục lưu kết quả tải về")

    # clear
    parser_clear = subparsers.add_parser("clear", help="Dọn dẹp phiên tải cũ")
    parser_clear.add_argument("--keep-history", action="store_true", help="Giữ lại lịch sử file CSV và bảng download_history")

    args = parser.parse_args()

    # Định tuyến lệnh tới hàm xử lý
    handlers = {
        "start-chrome": handle_start_chrome,
        "list-tabs": handle_list_tabs,
        "connect-tab": handle_connect_tab,
        "scrape": handle_scrape,
        "download": handle_download,
        "fill-names": handle_fill_names,
        "crawl": handle_crawl,
        "clear": handle_clear
    }

    handlers[args.command](args)

if __name__ == "__main__":
    main()
