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
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_download_dir, exist_ok=True)
        os.makedirs(self.temp_queue_dir, exist_ok=True)

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
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"download_dir": new_dir}, f, indent=4, ensure_ascii=False)
            self.update_download_dir(new_dir)
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

    def __init__(self):
        self.session_dir = settings.SESSION_DIR
        self.download_mode = "all"
        
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

