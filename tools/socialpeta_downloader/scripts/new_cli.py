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
    core = SocialPetaDownloaderCore(skip_db_init=True)
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
    
    base_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(csv_path))
    print(f"[*] Thư mục lưu kết quả: {base_dir}")

    import shutil

    # Chạy lần lượt các tiến trình tải tùy theo chế độ lọc
    if mode in ("all", "image"):
        print("[*] Đang tải hình ảnh...")
        img_out = os.path.join(base_dir, "download_images")
        core.downloader_service.run_download_images_cli(csv_path=csv_path, output_dir=img_out, max_workers=threads)
        
        # Tạo file CSV tương ứng
        print("[*] Đang tạo file CSV lọc riêng cho hình ảnh...")
        img_csv = os.path.join(base_dir, "download_images.csv")
        core.downloader_service.run_filter_image_creatives_cli(input_file=csv_path, output_file=img_csv)

    if mode in ("all", "cdn-video"):
        print("[*] Đang tải video CDN trực tiếp...")
        cdn_out = os.path.join(base_dir, "download_videos_not_youtube")
        core.downloader_service.run_download_videos_not_youtube_cli(csv_path=csv_path, output_dir=cdn_out, max_workers=threads)
        
        # Tạo file CSV tương ứng
        print("[*] Đang tạo file CSV lọc riêng cho video CDN...")
        cdn_csv = os.path.join(base_dir, "download_videos_not_youtube.csv")
        core.downloader_service.run_filter_cdn_video_creatives_cli(input_file=csv_path, output_file=cdn_csv)

    if mode in ("all", "youtube"):
        print("[*] Đang tải video YouTube...")
        yt_out = os.path.join(base_dir, "download_videos_youtube_only")
        core.youtube_service.run_download_video_youtube_only_cli(csv_path=csv_path, output_dir=yt_out, max_workers=threads)
        
        # Tạo file CSV tương ứng
        print("[*] Đang tạo file CSV lọc riêng cho video YouTube...")
        yt_csv = os.path.join(base_dir, "download_videos_youtube_only.csv")
        core.youtube_service.run_filter_youtube_creatives_cli(input_file=csv_path, output_file=yt_csv)

    print("[+] Hoàn tất tiến trình tải tài nguyên và tạo các file CSV phân loại.")

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
    core = SocialPetaDownloaderCore(skip_db_init=True)
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

def select_directory_gui(initial_dir):
    # Kiểm tra xem Tkinter có hoạt động bình thường không (bao gồm cả bản fix venv của core)
    tkinter_ok = False
    try:
        from socialpeta_downloader.core.utils import _fix_tcl_tk_env
        _fix_tcl_tk_env()
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
        tkinter_ok = True
    except Exception:
        pass

    # Nếu Tkinter hoạt động tốt, dùng hàm select_directory của core
    if tkinter_ok:
        try:
            from socialpeta_downloader.core.utils import select_directory
            res = select_directory(initial_dir=initial_dir, title="Chọn thư mục lưu trữ tải xuống")
            if res:
                return res
        except Exception:
            pass

    # Nếu Tkinter lỗi (ví dụ lỗi init.tcl trên Windows), fallback sang PowerShell dialog
    if sys.platform.startswith('win'):
        try:
            import subprocess
            initial_dir_escaped = initial_dir.replace("\\", "\\\\").replace('"', '\\"')
            ps_code = f"""
            Add-Type -AssemblyName System.Windows.Forms
            $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
            $dialog.Description = "Chọn thư mục lưu trữ tải xuống"
            $dialog.SelectedPath = "{initial_dir_escaped}"
            $dialog.ShowNewFolderButton = $true
            $win = New-Object System.Windows.Forms.Form
            $win.TopMost = $true
            $result = $dialog.ShowDialog($win)
            if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
                Write-Output $dialog.SelectedPath
            }}
            """
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo
            )
            stdout, stderr = proc.communicate(timeout=60)
            if proc.returncode == 0 and stdout.strip():
                return stdout.strip()
        except Exception:
            pass

    return None

def run_interactive_menu():
    from InquirerPy import inquirer
    from InquirerPy.base import Choice
    from playwright.sync_api import sync_playwright
    from socialpeta_downloader.core.utils import is_socialpeta_url
    # Initialize core (suppress migration prints to keep console clean)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        core = SocialPetaDownloaderCore(skip_db_init=True)
    
    # Auto detect Chrome status on port 9222
    chrome_service = ChromeService(context=core)
    if not chrome_service._is_chrome_cdp_active(9222):
        chrome_service.ensure_chrome_debug_port(9222)
        time.sleep(2)
        
    download_dir = core.download_dir
    pages_limit = 5
    
    while True:
        core.session_service.clear_session_data(clear_history=True)
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=========================================================")
        print("          SOCIALPETA DOWNLOADER INTERACTIVE CLI          ")
        print("=========================================================")
        print(f"  Thư mục lưu hiện tại: {download_dir}")
        print(f"  Số lượng trang tải:    {pages_limit}")
        print("=========================================================")
        
        choices = [
            Choice("1", "1. Tải hết (Videos, YouTube, Ảnh)"),
            Choice("2", "2. Chỉ tải YouTube"),
            Choice("3", "3. Chỉ tải ảnh"),
            Choice("4", "4. Thay đổi đường dẫn tải mặc định"),
            Choice("5", "5. Thay đổi số lượng trang tải mặc định"),
            Choice("exit", "6. Thoát")
        ]
        
        def safe_select(message, choices, default="1"):
            try:
                if not sys.stdin.isatty():
                    raise RuntimeError("Non-TTY environment")
                return inquirer.select(
                    message=message,
                    choices=choices,
                    default=default
                ).execute()
            except Exception:
                print(f"\n{message}")
                for choice in choices:
                    name = choice.name if hasattr(choice, "name") else str(choice)
                    print(f"  {name}")
                while True:
                    val = input(f"Chọn tùy chọn (mặc định '{default}'): ").strip()
                    val = val.replace('\ufeff', '').replace('\xef\xbb\xbf', '').strip()
                    if not val:
                        return default
                    for choice in choices:
                        c_val = choice.value if hasattr(choice, "value") else str(choice)
                        c_name = choice.name if hasattr(choice, "name") else str(choice)
                        if val == c_val or val == c_name.split('.')[0].strip():
                            return c_val
                    print("Lựa chọn không hợp lệ, vui lòng thử lại.")

        def safe_text(message, default=""):
            try:
                if not sys.stdin.isatty():
                    raise RuntimeError("Non-TTY environment")
                return inquirer.text(
                    message=message,
                    default=default
                ).execute()
            except Exception:
                val = input(f"{message} (mặc định '{default}'): ").strip()
                val = val.replace('\ufeff', '').replace('\xef\xbb\xbf', '').strip()
                return val if val else default

        try:
            choice = safe_select(
                message="Vui lòng chọn hành động bạn muốn thực hiện (Sử dụng mũi tên hoặc gõ số để chọn):",
                choices=choices,
                default="1"
            )
        except KeyboardInterrupt:
            print("\n[*] Đang thoát...")
            sys.exit(0)
            
        if choice == "exit":
            print("[*] Đang thoát...")
            break
            
        elif choice == "4":
            try:
                print("[*] Đang mở hộp thoại chọn thư mục...")
                selected_dir = select_directory_gui(download_dir)
                
                if selected_dir:
                    new_dir = os.path.abspath(selected_dir)
                    core.update_download_dir(new_dir)
                    core.save_config(new_dir)
                    download_dir = core.download_dir
                    print(f"[+] Đã cập nhật thư mục lưu: {download_dir}")
                else:
                    print("[-] Đã hủy chọn hoặc không thể mở hộp thoại. Bạn có muốn nhập thủ công không?")
                    use_manual = safe_select(
                        message="Chọn phương thức:",
                        choices=[
                            Choice("yes", "Có, nhập thủ công bằng tay"),
                            Choice("no", "Không, giữ nguyên thư mục cũ")
                        ],
                        default="no"
                    )
                    if use_manual == "yes":
                        new_dir = safe_text(
                            message="Nhập đường dẫn tải mới:",
                            default=download_dir
                        )
                        if new_dir:
                            new_dir = os.path.abspath(new_dir)
                            core.update_download_dir(new_dir)
                            core.save_config(new_dir)
                            download_dir = core.download_dir
                            print(f"[+] Đã cập nhật thư mục lưu: {download_dir}")
            except Exception as e:
                print(f"[-] Lỗi trong quá trình cập nhật thư mục: {e}")
                new_dir = safe_text(
                    message="Nhập đường dẫn tải mới:",
                    default=download_dir
                )
                if new_dir:
                    new_dir = os.path.abspath(new_dir)
                    core.update_download_dir(new_dir)
                    core.save_config(new_dir)
                    download_dir = core.download_dir
                    print(f"[+] Đã cập nhật thư mục lưu: {download_dir}")
            print("\nNhấn Enter để quay lại menu chính...")
            input()
                
        elif choice == "5":
            try:
                new_pages = safe_text(
                    message="Nhập số lượng trang tải mới (mặc định: 5):",
                    default=str(pages_limit)
                )
                if new_pages.isdigit() and int(new_pages) > 0:
                    pages_limit = int(new_pages)
                    print(f"[+] Đã cập nhật số trang tải: {pages_limit}")
                else:
                    print("[-] Giá trị nhập vào không hợp lệ.")
                print("\nNhấn Enter để quay lại menu chính...")
                input()
            except KeyboardInterrupt:
                pass
                
        elif choice in ("1", "2", "3"):
            csv_path = core.csv_path
            
            # Map choice to download_mode
            if choice == "1":
                download_mode = "all"
            elif choice == "2":
                download_mode = "youtube"
            else:
                download_mode = "image"
                
            print(f"[*] Chế độ tải: {download_mode}")
            print(f"[*] File CSV lưu tại: {csv_path}")
            print(f"[*] Thư mục tải xuống: {download_dir}")
            print(f"[*] Số lượng trang cần tải: {pages_limit}")
            
            try:
                # 1. Chạy cào dữ liệu từ trang 1 đến pages_limit bằng core
                print(f"[*] Bắt đầu cào dữ liệu sử dụng core từ trang 1 đến {pages_limit}...")
                core.youtube_service.run_scrape_pages_yt_cli(
                    start_page=1,
                    end_page=pages_limit,
                    csv_path=csv_path,
                    port=9222
                )
                
                # Điền tên file trước khi tải xuống để cập nhật cột video_name trong file CSV
                print(f"\n[*] Đang điền tên file thiếu cho CSV: {csv_path}...")
                core.fill_video_names_in_csv(csv_path)
                
                # 2. Tải các tài nguyên tương ứng từ CSV vào các thư mục con riêng biệt
                print(f"\n[*] Bắt đầu tải tài nguyên từ CSV...")
                if download_mode in ("all", "image"):
                    img_out = os.path.join(download_dir, "download_images")
                    core.downloader_service.run_download_images_cli(csv_path=csv_path, output_dir=img_out)
                    
                    # Tạo file CSV tương ứng
                    print("[*] Đang tạo file CSV lọc riêng cho hình ảnh...")
                    img_csv = os.path.join(download_dir, "download_images.csv")
                    core.downloader_service.run_filter_image_creatives_cli(input_file=csv_path, output_file=img_csv)

                if download_mode in ("all", "cdn-video"):
                    cdn_out = os.path.join(download_dir, "download_videos_not_youtube")
                    core.downloader_service.run_download_videos_not_youtube_cli(csv_path=csv_path, output_dir=cdn_out)
                    
                    # Tạo file CSV tương ứng
                    print("[*] Đang tạo file CSV lọc riêng cho video CDN...")
                    cdn_csv = os.path.join(download_dir, "download_videos_not_youtube.csv")
                    core.downloader_service.run_filter_cdn_video_creatives_cli(input_file=csv_path, output_file=cdn_csv)

                if download_mode in ("all", "youtube"):
                    yt_out = os.path.join(download_dir, "download_videos_youtube_only")
                    core.youtube_service.run_download_video_youtube_only_cli(csv_path=csv_path, output_dir=yt_out)
                    
                    # Tạo file CSV tương ứng
                    print("[*] Đang tạo file CSV lọc riêng cho video YouTube...")
                    yt_csv = os.path.join(download_dir, "download_videos_youtube_only.csv")
                    core.youtube_service.run_filter_youtube_creatives_cli(input_file=csv_path, output_file=yt_csv)
                
                
                print("\n[🏁] HOÀN TẤT LUỒNG TẢI DỮ LIỆU!")
                
                
            except Exception as e:
                import traceback
                print(f"[-] Lỗi trong quá trình cào/tải: {e}\n{traceback.format_exc()}")
                
            print("\nNhấn Enter để quay lại menu chính...")
            input()


def main():
    if len(sys.argv) == 1:
        run_interactive_menu()
        return

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
