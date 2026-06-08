# tools/socialpeta_downloader/core/__init__.py
"""
Responsibility: Orchestrator engine using composition to hold reference of services.
"""

import os
import queue
import threading
from typing import Any, Dict, List, Optional, Tuple
from socialpeta_downloader.config import settings
from socialpeta_downloader.sys_monitor import SystemMonitor

# Import new service classes
from socialpeta_downloader.core.protocols import IEngineContext
from socialpeta_downloader.core.utils import UtilsService
from socialpeta_downloader.core.chrome import ChromeService
from socialpeta_downloader.core.deduplication import DeduplicationService
from socialpeta_downloader.core.sniffer import SnifferService
from socialpeta_downloader.core.tab_manager import TabScanner
from socialpeta_downloader.core.downloader import DownloaderService, DynamicSemaphore
from socialpeta_downloader.core.youtube import YoutubeService
from socialpeta_downloader.core.legacy_sniffer import LegacySnifferService
from socialpeta_downloader.core.legacy_scraper import LegacyScraperService
from socialpeta_downloader.core.session import SessionService

class SocialPetaDownloaderCore:
    """
    Core engine orchestrated by composition instead of inheritance.
    """
    # Directory paths
    download_dir: str
    temp_json_path: str
    csv_path: str
    audit_csv_path: str
    temp_download_dir: str
    temp_queue_dir: str
    session_dir: str
    download_mode: str

    def get_default_download_dir(self) -> str:
        if os.name == 'nt':
            import winreg
            try:
                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                    downloads_dir = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
                    return os.path.join(downloads_dir, "SocialPeta_Downloader")
            except Exception:
                pass
        return os.path.join(os.path.expanduser("~"), "Downloads", "SocialPeta_Downloader")

    def update_download_dir(self, new_dir: str):
        old_download_dir = getattr(self, "download_dir", None)
        self.download_dir = new_dir
        self.temp_json_path = os.path.join(self.download_dir, "download_temp.json")
        self.csv_path = os.path.join(self.download_dir, "download_info.csv")
        self.audit_csv_path = os.path.join(self.download_dir, "duplicate_audit.csv")
        self.temp_download_dir = os.path.join(self.download_dir, ".temp_download")
        self.temp_queue_dir = os.path.join(self.download_dir, ".temp")
        
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            os.makedirs(self.temp_download_dir, exist_ok=True)
            os.makedirs(self.temp_queue_dir, exist_ok=True)
        except Exception as e:
            # Tự động chuyển về thư mục Downloads mặc định trên ổ C của Windows nếu đường dẫn/ổ đĩa không hợp lệ
            default_dir = self.get_default_download_dir()
            print(f"[-] Không thể tạo thư mục {new_dir}: {e}. Đang chuyển về thư mục mặc định: {default_dir}")
            self.download_dir = default_dir
            self.temp_json_path = os.path.join(self.download_dir, "download_temp.json")
            self.csv_path = os.path.join(self.download_dir, "download_info.csv")
            self.audit_csv_path = os.path.join(self.download_dir, "duplicate_audit.csv")
            self.temp_download_dir = os.path.join(self.download_dir, ".temp_download")
            self.temp_queue_dir = os.path.join(self.download_dir, ".temp")
            try:
                os.makedirs(self.download_dir, exist_ok=True)
                os.makedirs(self.temp_download_dir, exist_ok=True)
                os.makedirs(self.temp_queue_dir, exist_ok=True)
            except Exception as ex:
                print(f"[-] Lỗi nghiêm trọng: Không thể tạo thư mục mặc định {default_dir}: {ex}")

        if not getattr(self, "skip_db_init", False):
            if hasattr(self, "session_service") and self.session_service:
                self.session_service.init_db()
                self.session_service.migrate_old_data(old_download_dir)

    def load_config(self):
        import json
        config_path = os.path.join(settings.DATA_DIR, "config.json")
        default_dir = self.get_default_download_dir()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                stored_dir = cfg.get("download_dir")
                if stored_dir:
                    self.update_download_dir(stored_dir)
                    # Nếu xảy ra fallback trong update_download_dir, cập nhật lại config.json
                    if self.download_dir != stored_dir:
                        self.save_config(self.download_dir)
                    return
            except Exception as e:
                import traceback
                print(f"[-] Failed to load config: {e}\n{traceback.format_exc()}")
        self.update_download_dir(default_dir)

    def save_config(self, new_dir: str):
        import json
        config_path = os.path.join(settings.DATA_DIR, "config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        try:
            self.update_download_dir(new_dir)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"download_dir": self.download_dir}, f, indent=4, ensure_ascii=False)
        except Exception as e:
            import traceback
            self.log("error", f"[-] Failed to save config: {e}\n{traceback.format_exc()}")

    def scan_json_metadata_recursively(self) -> List[dict]:
        import sqlite3
        results = []
        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM download_history")
            rows = cursor.fetchall()
            cols = [col[0] for col in cursor.description]
            for r in rows:
                item = dict(zip(cols, r))
                item["status"] = "done"
                results.append(item)
        except Exception as e:
            import traceback
            self.log("error", f"[-] Error querying download_history: {e}\n{traceback.format_exc()}")
        finally:
            conn.close()
        return results

    def __init__(self, skip_db_init: bool = False):
        self.skip_db_init = skip_db_init
        self.session_dir = settings.SESSION_DIR
        self.download_mode = "all"
        self.quiet_mode = False
        
        # Load config to resolve self.download_dir and other paths
        self.load_config()
        
        # Ensure session directory exists
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Concurrency & Queues
        self.filter_queue = queue.Queue()  # (fpath, item)
        self.pending_downloads = queue.PriorityQueue()
        
        # Thread Locks
        self.naming_lock = threading.RLock()
        self.stt_lock = self.naming_lock
        self.history_lock = threading.RLock()
        self.metadata_lock = threading.RLock()
        self.item_locks = {}
        self.item_locks_lock = threading.Lock()
        self.stats = {
            "total_sniffed": 0,
            "pending": 0,
            "downloading": 0,
            "done": 0,
            "failed": 0,
            "expired": 0,
            "duplicate": 0
        }
        self.stats_lock = threading.Lock()
        
        # State Control
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start in running state
        self.running = False
        
        # Session STT counter
        self.stt_counter = 1
        
        # System Resource Control
        self.sys_monitor = SystemMonitor()
        self.download_semaphore = DynamicSemaphore(3)
        self.disk_full = False
        
        # Playwright CDP State
        self.playwright_connected = False
        
        # Tab tracking states
        self.tab_states = {}  # tab_index -> state dict
        self.tab_running_events = {}
        self.tab_packet_received_events = {}
        self.tab_last_packet_empty = {}
        self.item_status_cache = {}
        self.ad_id_to_status = {}
        self.tab_id_to_index = {}
        self.tab_is_new = {}
        self.download_progress = {}
        self.active_pages = {}
        self.tab_youtube_queues = {}
        self.active_page = None
        self.total_pages = None
        self.current_page = 1
        self.pagination_target_pages = 0
        self.last_packet_empty = False

        # Image deduplication cache
        self.image_md5_cache = {}
        
        # Logging Queue for WebSocket Streaming
        self.log_queue = queue.Queue()
        self.log_subscribers = []
        self.log_subscribers_lock = threading.Lock()

        # Additional queues and events for global state
        self.youtube_extract_queue = queue.Queue()
        self.page_packet_received = threading.Event()

        # Service composition initialization
        self.utils_service = UtilsService(self)
        self.chrome_service = ChromeService(self)
        self.deduplication_service = DeduplicationService(self)
        self.sniffer_service = SnifferService(self)
        self.tab_scanner = TabScanner(self)
        self.downloader_service = DownloaderService(self)
        self.youtube_service = YoutubeService(self)
        self.legacy_sniffer = LegacySnifferService(self)
        self.legacy_scraper = LegacyScraperService(self)
        self.session_service = SessionService(self)

        # Initialize SQLite database and migrate old CSV/JSON files
        if not skip_db_init:
            self.session_service.init_db()
            self.session_service.migrate_old_data()

            # Initialize Image MD5 Cache
            self.deduplication_service._init_image_md5_cache()


    # Delegation methods to satisfy IEngineContext protocol
    def log(self, level: str, message: str) -> None:
        self.utils_service.log(level, message)

    def get_db_path(self) -> str:
        return self.utils_service.get_db_path()

    def get_item_lock(self, fpath: str):
        return self.utils_service.get_item_lock(fpath)

    def db_get_item(self, ad_id: str) -> Optional[dict]:
        return self.utils_service.db_get_item(ad_id)

    def db_get_item_by_fpath(self, fpath: str) -> Optional[dict]:
        return self.utils_service.db_get_item_by_fpath(fpath)

    def _write_item_file(self, fpath: str, item: dict) -> None:
        self.utils_service._write_item_file(fpath, item)

    def _save_item_state(self, item: dict) -> None:
        self.utils_service._save_item_state(item)

    def clean_app_name(self, app_name: str) -> str:
        return self.utils_service.clean_app_name(app_name)

    def get_unique_filename(self, app_name: str) -> Tuple[str, int]:
        return self.utils_service.get_unique_filename(app_name)

    def get_unique_image_filename(self, app_name: str, url: str) -> Tuple[str, int]:
        return self.utils_service.get_unique_image_filename(app_name, url)

    def clean_filename(self, filename: str) -> str:
        return self.utils_service.clean_filename(filename)

    def extract_ad_id(self, url: str) -> str:
        return self.utils_service.extract_ad_id(url)

    # Public interface delegation methods
    def check_and_launch_chrome(self, port: Optional[int] = None) -> bool:
        return self.chrome_service.check_and_launch_chrome(port)

    def check_login_status(self, port: Optional[int] = None) -> bool:
        return self.chrome_service.check_login_status(port)

    def run_login_flow(self, port: Optional[int] = None) -> bool:
        return self.chrome_service.run_login_flow(port)

    def clear_logs(self) -> None:
        self.utils_service.clear_logs()

    def start_system(self, thread_count: int = 3) -> None:
        self.downloader_service.start_system(thread_count)

    def stop_system(self) -> None:
        self.downloader_service.stop_system()

    def detect_tabs(self, port: Optional[int] = None) -> list:
        return self.tab_scanner.detect_tabs(port)

    def run_tab_scraper(self, tab_index: int, total_pages: int, port: Optional[int] = None) -> None:
        self.tab_scanner.run_tab_scraper(tab_index, total_pages, port)

    def soft_trigger(self, tab_index: int) -> None:
        self.sniffer_service.soft_trigger(tab_index)

    def download_single_ad(self, url: str) -> dict:
        return self.legacy_scraper.download_single_ad(url)

    def scrape_search_page_and_download(self, url: str, max_results: int = 10) -> List[dict]:
        return self.legacy_scraper.scrape_search_page_and_download(url, max_results)

    def get_current_page(self, page) -> int:
        return self.utils_service.get_current_page(page)

    def scroll_to_bottom(self, page, scroll_delay: float = 0.5) -> None:
        self.utils_service.scroll_to_bottom(page, scroll_delay)

    def connect_to_active_tab(self, playwright, port: int = 9222):
        return self.tab_scanner.connect_to_active_tab(playwright, port)

    def custom_click_and_extract_youtube_from_page(self, page) -> list:
        return self.youtube_service.custom_click_and_extract_youtube_from_page(page)

    def append_to_custom_csv(self, filepath: str, item: dict) -> None:
        """
        Ghi thêm một bản ghi quảng cáo vào file CSV tùy chỉnh (ủy quyền qua SessionService).
        """
        self.session_service.append_to_custom_csv(filepath, item)

    def clear_session_data(self, clear_history: bool = True) -> None:
        """
        Dọn dẹp cơ sở dữ liệu SQLite, xóa file JSON tạm thời và thư mục tải tạm.
        """
        self.session_service.clear_session_data(clear_history)

    def run_crawler_cli(self, argv: List[str]) -> None:
        import os
        import sys
        import time
        import threading
        
        print("[*] Khoi chay SocialPeta Downloader Core...")
        
        # Check command line arguments for page count
        pages_to_scrape = 10
        if len(argv) > 1:
            try:
                pages_to_scrape = int(argv[1])
                print(f"[*] Thiet lap so trang can cao: {pages_to_scrape}")
            except ValueError:
                print(f"[!] Tham so trang khong hop le: {argv[1]}. Mac dinh la 10.")
                
        # 5 downloader threads as requested
        print("[*] Khoi dong he thong voi 5 luong...")
        self.start_system(thread_count=5)
        
        print("[*] Dang quet cac tab dang hoat dong trong Chrome...")
        active_tabs = self.detect_tabs()
        if not active_tabs:
            print("[-] Khong tim thay tab SocialPeta nao. Vui long kiem tra lai Chrome.")
            self.stop_system()
            return

        # Start scraping pages for each active tab
        threads = []
        for tab in active_tabs:
            idx = tab["index"]
            print(f"[*] Bat dau cao tab [{idx}] - {pages_to_scrape} trang...")
            t = threading.Thread(target=self.run_tab_scraper, args=(idx, pages_to_scrape), daemon=True)
            t.start()
            threads.append(t)
            
        try:
            while self.running:
                # Print stats every 5 seconds
                if sys.stdout.isatty():
                    os.system('cls' if os.name == 'nt' else 'clear')
                print("==================================================")
                print("         STATUS MONITOR (NON-INTERACTIVE)         ")
                print("==================================================")
                
                scrapers_alive = any(t.is_alive() for t in threads)
                
                # Get pending and downloading counts from in-memory stats
                pending = self.stats.get("pending", 0)
                downloading = self.stats.get("downloading", 0)
                
                stats = self.stats
                print(f"  - Scrapers running: {scrapers_alive}")
                print(f"  - Total sniffed:    {stats['total_sniffed']}")
                print(f"  - Waiting:          {pending}")
                print(f"  - Downloading:      {downloading}")
                print(f"  - Saved (Unique):   {stats['done']}")
                print(f"  - Failed:           {stats['failed']}")
                print(f"  - Expired:          {stats['expired']}")
                print(f"  - Duplicate:        {stats['duplicate']}")
                print("==================================================")
                
                # Check if all scrapers are finished and queues are empty
                if not scrapers_alive and pending == 0 and downloading == 0:
                    print("[+] Tat ca luong scraper da hoan thanh va file da tai xong!")
                    break
                    
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("[*] Nguoi dung yeu cau dung...")
        finally:
            print("[*] Dang dung SocialPeta Downloader Engine...")
            self.stop_system()
            print("[+] Da dung SocialPeta Downloader.")

    def fill_video_names_in_csv(self, csv_path: str) -> int:
        """
        Điền các video_name còn thiếu trong file CSV chỉ định sử dụng logic đặt tên của core.
        Trả về số dòng đã được điền.
        """
        import csv
        if not os.path.exists(csv_path):
            self.log("error", f"[-] Không tìm thấy file CSV tại: {csv_path}")
            return 0

        # Đọc file CSV
        rows = []
        fieldnames = []
        try:
            with open(csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)
        except Exception as e:
            self.log("error", f"[-] Lỗi đọc file CSV: {e}")
            return 0

        self.log("info", f"[*] Đã đọc {len(rows)} dòng từ {csv_path}")
        
        filled_count = 0
        for row in rows:
            video_name = row.get("video_name", "").strip()
            if not video_name:
                media_type = row.get("media_type", "").strip().lower()
                app_name = row.get("app_name", "").strip() or "UnknownApp"
                image_url = row.get("image_url", "").strip()
                
                if media_type in ("image", "youtube_thumbnail"):
                    filename, _ = self.get_unique_image_filename(app_name, image_url)
                else:
                    filename, _ = self.get_unique_filename(app_name)
                    
                row["video_name"] = filename
                filled_count += 1

        if filled_count > 0:
            # Ghi lại file CSV
            try:
                with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                self.log("info", f"[+] Đã điền thành công {filled_count} video_name vào file CSV.")
            except Exception as e:
                self.log("error", f"[-] Lỗi ghi file CSV: {e}")
        else:
            self.log("info", "[*] Không có video_name nào cần điền.")
            
        return filled_count

    def run_download_cli(
        self,
        csv_path: str,
        output_dir: Optional[str] = None,
        mode: str = "all",
        threads: int = 3
    ) -> None:
        """
        CLI để tải tài nguyên hình ảnh / video từ file CSV với cấu hình linh hoạt.
        """
        import sys
        if not os.path.exists(csv_path):
            print(f"[-] LỖI: File CSV không tồn tại tại: {csv_path}")
            sys.exit(1)

        print(f"[*] Bắt đầu tiến trình tải tài nguyên từ CSV: {csv_path}")
        print(f"[*] Chế độ tải: {mode} | Luồng tối đa: {threads}")
        
        base_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(csv_path))
        print(f"[*] Thư mục lưu kết quả: {base_dir}")

        if mode in ("all", "image"):
            print("[*] Đang tải hình ảnh...")
            img_out = os.path.join(base_dir, "download_images")
            self.downloader_service.run_download_images_cli(csv_path=csv_path, output_dir=img_out, max_workers=threads)
            
            print("[*] Đang tạo file CSV lọc riêng cho hình ảnh...")
            img_csv = os.path.join(base_dir, "download_images.csv")
            self.downloader_service.run_filter_image_creatives_cli(input_file=csv_path, output_file=img_csv)

        if mode in ("all", "cdn-video"):
            print("[*] Đang tải video CDN trực tiếp...")
            cdn_out = os.path.join(base_dir, "download_videos_not_youtube")
            self.downloader_service.run_download_videos_not_youtube_cli(csv_path=csv_path, output_dir=cdn_out, max_workers=threads)
            
            print("[*] Đang tạo file CSV lọc riêng cho video CDN...")
            cdn_csv = os.path.join(base_dir, "download_videos_not_youtube.csv")
            self.downloader_service.run_filter_cdn_video_creatives_cli(input_file=csv_path, output_file=cdn_csv)

        if mode in ("all", "youtube"):
            print("[*] Đang tải video YouTube...")
            yt_out = os.path.join(base_dir, "download_videos_youtube_only")
            self.youtube_service.run_download_video_youtube_only_cli(csv_path=csv_path, output_dir=yt_out, max_workers=threads)
            
            print("[*] Đang tạo file CSV lọc riêng cho video YouTube...")
            yt_csv = os.path.join(base_dir, "download_videos_youtube_only.csv")
            self.youtube_service.run_filter_youtube_creatives_cli(input_file=csv_path, output_file=yt_csv)

        print("[+] Hoàn tất tiến trình tải tài nguyên và tạo các file CSV phân loại.")

    def run_crawl_cli(
        self,
        pages: int = 10,
        threads: int = 5,
        output_dir: Optional[str] = None
    ) -> None:
        """
        CLI để chạy luồng cào và tải tự động hoàn toàn (Full Flow) với giao diện giám sát tiến độ.
        """
        import sys
        import time
        
        if output_dir:
            self.update_download_dir(output_dir)

        print(f"[*] Khởi chạy SocialPeta Downloader Core với {threads} luồng...")
        self.start_system(thread_count=threads)
        
        print("[*] Đang quét các tab đang hoạt động trong Chrome...")
        active_tabs = self.detect_tabs()
        if not active_tabs:
            print("[-] Không tìm thấy tab SocialPeta nào. Vui lòng kiểm tra lại Chrome.")
            self.stop_system()
            sys.exit(1)
            
        crawl_threads = []
        for tab in active_tabs:
            idx = tab["index"]
            print(f"[*] Bắt đầu cào tab [{idx}] - {pages} trang...")
            t = threading.Thread(target=self.run_tab_scraper, args=(idx, pages), daemon=True)
            t.start()
            crawl_threads.append(t)
            
        try:
            while self.running:
                if sys.stdout.isatty():
                    os.system('cls' if os.name == 'nt' else 'clear')
                print("==================================================")
                print("         STATUS MONITOR (NON-INTERACTIVE)         ")
                print("==================================================")
                
                scrapers_alive = any(t.is_alive() for t in crawl_threads)
                pending = self.stats.get("pending", 0)
                downloading = self.stats.get("downloading", 0)
                stats = self.stats
                
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
                    print("[+] Tất cả luồng scraper đã hoàn thành và file đã tải xong!")
                    break
                    
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("[*] Người dùng yêu cầu dừng...")
        finally:
            print("[*] Đang dừng SocialPeta Downloader Engine...")
            self.stop_system()
            print("[+] Đã dừng SocialPeta Downloader.")

    def run_interactive_menu(self) -> None:
        """
        Khởi chạy menu tương tác (Interactive CLI TUI) sử dụng InquirerPy.
        """
        from InquirerPy import inquirer
        from InquirerPy.base import Choice
        import contextlib
        import io
        import sys
        import time

        print("[*] Đang khởi động hệ thống...", end="\r", flush=True)
        with contextlib.redirect_stdout(io.StringIO()):
            pass
        
        # Auto detect Chrome status on port 9222
        chrome_service = self.chrome_service
        if not chrome_service._is_chrome_cdp_active(9222):
            print("[*] Đang khởi chạy Chrome debug (cổng 9222)...", end="\r", flush=True)
            chrome_service.ensure_chrome_debug_port(9222)
            time.sleep(2)
            
        download_dir = self.download_dir
        pages_limit = 5
        
        while True:
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
                    selected_dir = self.utils_service.select_directory_gui(download_dir)
                    
                    if selected_dir:
                        new_dir = os.path.abspath(selected_dir)
                        self.update_download_dir(new_dir)
                        self.save_config(new_dir)
                        download_dir = self.download_dir
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
                                self.update_download_dir(new_dir)
                                self.save_config(new_dir)
                                download_dir = self.download_dir
                                print(f"[+] Đã cập nhật thư mục lưu: {download_dir}")
                except Exception as e:
                    print(f"[-] Lỗi trong quá trình cập nhật thư mục: {e}")
                    new_dir = safe_text(
                        message="Nhập đường dẫn tải mới:",
                        default=download_dir
                    )
                    if new_dir:
                        new_dir = os.path.abspath(new_dir)
                        self.update_download_dir(new_dir)
                        self.save_config(new_dir)
                        download_dir = self.download_dir
                        print(f"[+] Đã cập nhật thư mục lưu: {download_dir}")
                time.sleep(1.5)
                    
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
                    time.sleep(1.5)
                except KeyboardInterrupt:
                    pass
                    
            elif choice in ("1", "2", "3"):
                csv_path = self.csv_path
                
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
                    print(f"[*] Bắt đầu cào dữ liệu từ trang 1 đến {pages_limit}...")
                    self.youtube_service.run_scrape_pages_yt_cli(
                        start_page=1,
                        end_page=pages_limit,
                        csv_path=csv_path,
                        port=9222
                    )
                    
                    print(f"\n[*] Đang điền tên file thiếu cho CSV: {csv_path}...")
                    self.fill_video_names_in_csv(csv_path)
                    
                    print(f"\n[*] Bắt đầu tải tài nguyên từ CSV...")
                    if download_mode in ("all", "image"):
                        img_out = os.path.join(download_dir, "download_images")
                        self.downloader_service.run_download_images_cli(csv_path=csv_path, output_dir=img_out)
                        
                        print("[*] Đang tạo file CSV lọc riêng cho hình ảnh...")
                        img_csv = os.path.join(download_dir, "download_images.csv")
                        self.downloader_service.run_filter_image_creatives_cli(input_file=csv_path, output_file=img_csv)

                    if download_mode in ("all", "cdn-video"):
                        cdn_out = os.path.join(download_dir, "download_videos_not_youtube")
                        self.downloader_service.run_download_videos_not_youtube_cli(csv_path=csv_path, output_dir=cdn_out)
                        
                        print("[*] Đang tạo file CSV lọc riêng cho video CDN...")
                        cdn_csv = os.path.join(download_dir, "download_videos_not_youtube.csv")
                        self.downloader_service.run_filter_cdn_video_creatives_cli(input_file=csv_path, output_file=cdn_csv)

                    if download_mode in ("all", "youtube"):
                        yt_out = os.path.join(download_dir, "download_videos_youtube_only")
                        self.youtube_service.run_download_video_youtube_only_cli(csv_path=csv_path, output_dir=yt_out)
                        
                        print("[*] Đang tạo file CSV lọc riêng cho video YouTube...")
                        yt_csv = os.path.join(download_dir, "download_videos_youtube_only.csv")
                        self.youtube_service.run_filter_youtube_creatives_cli(input_file=csv_path, output_file=yt_csv)
                        
                    print("\n[🏁] HOÀN TẤT LUỒNG TẢI DỮ LIỆU!")
                    self.clear_sqlite_only()
                except Exception as e:
                    import traceback
                    print(f"[-] Lỗi trong quá trình cào/tải: {e}\n{traceback.format_exc()}")
                    
                print("\nNhấn Enter để quay lại menu chính...")
                input()

    def clear_sqlite_only(self) -> None:
        """
        Chỉ xóa cơ sở dữ liệu SQLite (db.sqlite3) và các file WAL/SHM liên quan.
        """
        self.session_service.clear_sqlite_only()


