import os
import queue
import threading
from socialpeta_downloader.config import settings
from socialpeta_downloader.sys_monitor import SystemMonitor

# Import mixins
from socialpeta_downloader.core.utils import UtilsMixin
from socialpeta_downloader.core.chrome import ChromeMixin
from socialpeta_downloader.core.deduplication import DedupMixin
from socialpeta_downloader.core.sniffer import SnifferMixin
from socialpeta_downloader.core.tab_manager import TabManagerMixin
from socialpeta_downloader.core.downloader import DownloaderMixin, DynamicSemaphore
from socialpeta_downloader.core.youtube import YoutubeMixin
from socialpeta_downloader.core.legacy_sniffer import LegacySnifferMixin
from socialpeta_downloader.core.legacy_scraper import LegacyScraperMixin
from socialpeta_downloader.core.session import SessionMixin

class SocialPetaDownloaderCore(
    UtilsMixin,
    ChromeMixin,
    DedupMixin,
    SnifferMixin,
    TabManagerMixin,
    DownloaderMixin,
    YoutubeMixin,
    LegacySnifferMixin,
    LegacyScraperMixin,
    SessionMixin
):
    """
    Core engine that combines functionalities via Mixin inheritance.
    """
    def get_default_download_dir(self) -> str:
        import sys
        if getattr(sys, 'frozen', False):
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
        else:
            return r"D:\Python\my_tools\data\videos"

    def update_download_dir(self, new_dir: str):
        self.download_dir = new_dir
        self.temp_json_path = os.path.join(self.download_dir, "download_temp.json")
        self.csv_path = os.path.join(self.download_dir, "download_info.csv")
        self.audit_csv_path = os.path.join(self.download_dir, "duplicate_audit.csv")
        self.temp_download_dir = os.path.join(self.download_dir, ".temp_download")
        self.temp_queue_dir = os.path.join(self.download_dir, ".temp")
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.temp_download_dir, exist_ok=True)
        os.makedirs(self.temp_queue_dir, exist_ok=True)

    def load_config(self):
        import json
        config_path = os.path.join(settings.ROOT_DIR, "data", "config.json")
        default_dir = self.get_default_download_dir()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                stored_dir = cfg.get("download_dir")
                if stored_dir:
                    self.update_download_dir(stored_dir)
                    return
            except Exception:
                pass
        self.update_download_dir(default_dir)

    def save_config(self, new_dir: str):
        import json
        config_path = os.path.join(settings.ROOT_DIR, "data", "config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"download_dir": new_dir}, f, indent=4, ensure_ascii=False)
            self.update_download_dir(new_dir)
        except Exception as e:
            print(f"[-] Failed to save config: {e}")

    def scan_json_metadata_recursively(self) -> list[dict]:
        import json
        results = {}
        if not os.path.exists(self.download_dir):
            return []
        
        for root, dirs, files in os.walk(self.download_dir):
            for file in files:
                if file.endswith(".json") and not file.endswith(".tmp") and file != "config.json" and file != "download_temp.json":
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            item = json.load(f)
                        ad_id = item.get("ad_id")
                        if ad_id:
                            existing = results.get(ad_id)
                            if not existing:
                                results[ad_id] = item
                            else:
                                if item.get("status") == "done" and existing.get("status") != "done":
                                    results[ad_id] = item
                                elif item.get("status") == existing.get("status"):
                                    item_time = item.get("download_time", "")
                                    existing_time = existing.get("download_time", "")
                                    if item_time > existing_time:
                                        results[ad_id] = item
                    except Exception:
                        pass
        return list(results.values())

    def __init__(self):
        self.session_dir = settings.SESSION_DIR
        
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
        self.last_packet_empty = False

        # Image deduplication cache
        self.image_md5_cache = {}
        self._init_image_md5_cache()
        
        # Logging Queue for WebSocket Streaming
        self.log_queue = queue.Queue()
        self.log_subscribers = []
        self.log_subscribers_lock = threading.Lock()

        # Additional queues and events for global state
        self.youtube_extract_queue = queue.Queue()
        self.page_packet_received = threading.Event()
