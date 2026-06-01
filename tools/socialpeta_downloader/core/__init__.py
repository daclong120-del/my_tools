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
    def __init__(self):
        self.download_dir = settings.DOWNLOAD_DIR
        self.session_dir = settings.SESSION_DIR
        
        # Paths
        self.temp_json_path = os.path.join(self.download_dir, "download_temp.json")
        self.csv_path = os.path.join(self.download_dir, "download_info.csv")
        self.audit_csv_path = os.path.join(self.download_dir, "duplicate_audit.csv")
        self.temp_download_dir = os.path.join(self.download_dir, ".temp_download")
        self.temp_queue_dir = os.path.join(self.download_dir, ".temp")
        
        # Ensure directories exist
        os.makedirs(self.download_dir, exist_ok=True)
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.temp_download_dir, exist_ok=True)
        os.makedirs(self.temp_queue_dir, exist_ok=True)
        
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
