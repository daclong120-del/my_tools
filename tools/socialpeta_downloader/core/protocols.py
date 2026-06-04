from typing import Protocol, Any, Dict, List, Optional, Tuple
import queue
import threading

class IEngineContext(Protocol):
    """
    Giao diện đại diện cho ngữ cảnh hoạt động của công cụ tải xuống SocialPeta (Engine Context).
    """
    # Directories
    download_dir: str
    temp_queue_dir: str
    temp_download_dir: str
    session_dir: str
    csv_path: str
    audit_csv_path: str
    download_mode: str
    quiet_mode: bool
    
    # State control
    running: bool
    pause_event: threading.Event
    disk_full: bool
    stt_counter: int
    playwright_connected: bool
    last_packet_empty: bool
    total_pages: Optional[int]
    current_page: int
    pagination_target_pages: int
    active_page: Any
    
    # Stats
    stats: Dict[str, int]
    stats_lock: threading.Lock
    
    # Queues
    filter_queue: queue.Queue
    pending_downloads: queue.PriorityQueue
    log_queue: queue.Queue
    log_subscribers: List[queue.Queue]
    log_subscribers_lock: threading.Lock
    youtube_extract_queue: queue.Queue
    page_packet_received: threading.Event
    
    # Locks
    naming_lock: threading.RLock
    stt_lock: threading.RLock
    history_lock: threading.RLock
    metadata_lock: threading.RLock
    item_locks: Dict[str, List[Any]]
    item_locks_lock: threading.Lock
    download_semaphore: Any
    
    # Tab states
    tab_states: Dict[int, Dict[str, Any]]
    tab_running_events: Dict[int, threading.Event]
    tab_packet_received_events: Dict[int, threading.Event]
    tab_last_packet_empty: Dict[int, bool]
    tab_youtube_queues: Dict[int, queue.Queue]
    active_pages: Dict[int, Any]
    item_status_cache: Dict[str, str]
    image_md5_cache: Dict[str, str]
    ad_id_to_status: Dict[str, str]
    tab_id_to_index: Dict[str, int]
    tab_is_new: Dict[str, bool]
    download_progress: Dict[str, Any]
    
    # Services
    sys_monitor: Any
    chrome_service: Any
    downloader_service: Any
    tab_scanner: Any
    deduplication_service: Any
    youtube_service: Any
    sniffer_service: Any
    session_service: Any
    legacy_sniffer: Any
    legacy_scraper: Any
    utils_service: Any

    # hàm đã hoạt động rồi đừng động vào
    def log(self, level: str, message: str) -> None: ...
    # hàm đã hoạt động rồi đừng động vào
    def get_db_path(self) -> str: ...
    # hàm đã hoạt động rồi đừng động vào
    def get_item_lock(self, fpath: str) -> Any: ...
    # hàm đã hoạt động rồi đừng động vào
    def db_get_item(self, ad_id: str) -> Optional[dict]: ...
    # hàm đã hoạt động rồi đừng động vào
    def db_get_item_by_fpath(self, fpath: str) -> Optional[dict]: ...
    # hàm đã hoạt động rồi đừng động vào
    def _write_item_file(self, fpath: str, item: dict) -> None: ...
    # hàm đã hoạt động rồi đừng động vào
    def _save_item_state(self, item: dict) -> None: ...
    # hàm đã hoạt động rồi đừng động vào
    def clean_app_name(self, app_name: str) -> str: ...
    # hàm đã hoạt động rồi đừng động vào
    def get_unique_filename(self, app_name: str) -> Tuple[str, int]: ...
    # hàm đã hoạt động rồi đừng động vào
    def get_unique_image_filename(self, app_name: str, url: str) -> Tuple[str, int]: ...
    # hàm đã hoạt động rồi đừng động vào
    def clean_filename(self, filename: str) -> str: ...
    # hàm đã hoạt động rồi đừng động vào
    def extract_ad_id(self, url: str) -> str: ...
