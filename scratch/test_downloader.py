import os
import sys
import time
import shutil
import queue
import unittest
import threading
from typing import Any, Tuple, Optional
from unittest.mock import patch, MagicMock

# Add tools to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))

from socialpeta_downloader.core.downloader import DynamicSemaphore, DownloaderService
from socialpeta_downloader.core.protocols import IEngineContext

class MockUtilsService:
    def __init__(self):
        self.logs = []
    def log(self, level, message):
        self.logs.append((level, message))
        print(f"[{level.upper()}] {message}")
    def _is_ad_already_downloaded(self, ad_id):
        return False
    def _is_ad_already_downloading_or_done(self, ad_id, exclude_path=None):
        return False
    def _save_item_state(self, item):
        pass
    def get_unique_image_filename(self, app_name, url):
        return f"{app_name}_img.png", 1
    def get_unique_filename(self, app_name):
        return f"{app_name}_vid.mp4", 1
    def db_get_item(self, ad_id):
        return {"ad_id": ad_id, "media_type": "video", "status": "pending"}
    def _write_item_file(self, path, item):
        pass
    def resolve_saved_path(self, saved_path):
        return saved_path

class MockSessionService:
    def __init__(self):
        self.audit_csv = []
        self.csv = []
        self.master_urls = {}
        self.restored = False
    def append_to_audit_csv(self, ad_id, app_name, dup_ad_id, reason):
        self.audit_csv.append((ad_id, app_name, dup_ad_id, reason))
    def append_to_csv(self, item):
        self.csv.append(item)
    def update_master_youtube_url(self, dup_ad_id, youtube_url):
        self.master_urls[dup_ad_id] = youtube_url
    def restore_session(self):
        self.restored = True

class MockSysMonitor:
    def __init__(self):
        self.max_threads_user = 3
        self.started = False
        self.stopped = False
    def start(self):
        self.started = True
    def stop(self):
        self.stopped = True
    def get_stats(self):
        return {
            "ram_usage": 50.0,
            "low_ram_system": False,
            "max_threads_recommended": 3
        }

class MockDeduplicationService:
    def __init__(self):
        self.dup_results = {}
        self.durations = {}
    def _get_file_md5(self, path):
        return "mock_md5"
    def check_duplicate(self, path):
        return self.dup_results.get(path, (False, "", "no dup"))
    def get_video_duration(self, path):
        return self.durations.get(path, 10.0)

class MockEngineContext:
    def __init__(self):
        self.download_dir = "mock_download"
        self.temp_download_dir = "mock_temp_download"
        self.temp_queue_dir = "mock_temp_queue"
        self.session_dir = "mock_session"
        self.download_mode = "all"
        self.quiet_mode = False
        self.running = True
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.disk_full = False
        self.stats = {"pending": 0, "downloading": 0}
        self.stats_lock = threading.Lock()
        
        self.filter_queue = queue.Queue()
        self.download_semaphore = DynamicSemaphore(3)
        self.pending_downloads = queue.Queue()
        
        self.history_lock = threading.RLock()
        self.naming_lock = threading.RLock()
        self.stt_lock = threading.RLock()
        self.metadata_lock = threading.RLock()
        self.item_locks = {}
        self.item_locks_lock = threading.Lock()
        
        self.image_md5_cache = {}
        self.download_progress = {}
        self.tab_running_events = {}
        
        self.utils_service = MockUtilsService()
        self.session_service = MockSessionService()
        self.sys_monitor = MockSysMonitor()
        self.deduplication_service = MockDeduplicationService()
        
        self.items_db = {}
        
    def get_item_lock(self, fpath):
        with self.item_locks_lock:
            if fpath not in self.item_locks:
                self.item_locks[fpath] = threading.RLock()
            return self.item_locks[fpath]
            
    def db_get_item_by_fpath(self, fpath):
        return self.items_db.get(fpath)
        
    def _write_item_file(self, fpath, item):
        pass
        
    def _save_item_state(self, item):
        fpath = item.get("fpath")
        if fpath:
            self.items_db[fpath] = item

    def get_db_path(self):
        return "mock_db.sqlite3"

class TestDownloaderFunctions(unittest.TestCase):
    def setUp(self):
        self.context = MockEngineContext()
        self.service = DownloaderService(self.context)
        # Create temp dirs
        os.makedirs(self.context.download_dir, exist_ok=True)
        os.makedirs(self.context.temp_download_dir, exist_ok=True)

    def tearDown(self):
        # Cleanup mock dirs
        if os.path.exists(self.context.download_dir):
            shutil.rmtree(self.context.download_dir)
        if os.path.exists(self.context.temp_download_dir):
            shutil.rmtree(self.context.temp_download_dir)

    def test_1_dynamic_semaphore(self):
        """Test DynamicSemaphore capacity adjustment and locking behavior."""
        sem = DynamicSemaphore(2)
        self.assertEqual(sem.value, 2)
        
        # Test basic acquire/release
        sem.acquire()
        self.assertEqual(sem.active_count, 1)
        sem.acquire()
        self.assertEqual(sem.active_count, 2)
        
        # Set new value and check release behavior
        sem.set_value(3)
        sem.acquire()
        self.assertEqual(sem.active_count, 3)
        
        sem.release()
        self.assertEqual(sem.active_count, 2)
        sem.release()
        sem.release()
        self.assertEqual(sem.active_count, 0)
        print("✅ DynamicSemaphore verified successfully.")

    @patch('requests.get')
    def test_2_download_image_file(self, mock_get):
        """Test image downloading from url."""
        # 1. Success case
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"fake_image_data_chunk"]
        mock_get.return_value = mock_response
        
        dest = os.path.join(self.context.temp_download_dir, "test_img.png")
        success = self.service.download_image_file("https://example.com/img.png", dest)
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(dest))
        with open(dest, 'rb') as f:
            self.assertEqual(f.read(), b"fake_image_data_chunk")
            
        # 2. Failure case
        mock_response.status_code = 404
        success = self.service.download_image_file("https://example.com/img.png", dest + "_fail")
        self.assertFalse(success)
        print("✅ download_image_file verified successfully.")

    @patch('requests.get')
    def test_3_download_worker_image(self, mock_get):
        """Test _download_worker for an image item."""
        # Setup mock request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"some_img_bytes"]
        mock_get.return_value = mock_response
        
        # Setup item in mock db
        item = {
            "ad_id": "12345",
            "media_type": "image",
            "status": "pending",
            "image_url": "https://example.com/img.png",
            "app_name": "TestApp"
        }
        fpath = os.path.join(self.context.temp_download_dir, "12345.json")
        self.context.items_db[fpath] = item
        
        # Push to pending downloads
        self.context.pending_downloads.put((1, fpath))
        
        # Run worker once
        # We start worker in a thread but wait for it to process
        t = threading.Thread(target=self.service._download_worker)
        t.daemon = True
        t.start()
        
        # Wait a bit
        time.sleep(0.5)
        # Stop context running to break worker loop
        self.context.running = False
        t.join(timeout=1.0)
        
        # Verify result
        updated_item = self.context.items_db[fpath]
        self.assertEqual(updated_item["status"], "done")
        self.assertEqual(updated_item["video_name"], "TestApp_img.png")
        self.assertTrue(os.path.exists(updated_item["saved_path"]))
        print("✅ _download_worker image mode verified successfully.")

    @patch('requests.get')
    def test_4_download_worker_cdn_video(self, mock_get):
        """Test _download_worker for a CDN video item."""
        self.context.running = True
        # Setup mock request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '14'}
        mock_response.iter_content.return_value = [b"some_cdn_bytes"]
        mock_get.return_value = mock_response
        
        # Setup item in mock db
        item = {
            "ad_id": "67890",
            "media_type": "video",
            "status": "pending",
            "video_url": "https://example.com/video.mp4",
            "app_name": "TestApp"
        }
        fpath = os.path.join(self.context.temp_download_dir, "67890.json")
        self.context.items_db[fpath] = item
        
        # Push to pending downloads
        self.context.pending_downloads.put((1, fpath))
        
        # Run worker once
        t = threading.Thread(target=self.service._download_worker)
        t.daemon = True
        t.start()
        
        # Wait a bit
        time.sleep(0.5)
        self.context.running = False
        t.join(timeout=1.0)
        
        # Verify it downloaded and placed in filter_queue
        self.assertFalse(self.context.filter_queue.empty())
        queued_item = self.context.filter_queue.get()
        self.assertEqual(queued_item["status"], "downloaded")
        self.assertTrue(os.path.exists(queued_item["saved_path"]))
        print("✅ _download_worker CDN video mode verified successfully.")

    @patch('subprocess.run')
    def test_5_stream_3_dedup_filter_unique(self, mock_sub_run):
        """Test stream_3_dedup_filter when item is unique."""
        # Mock ffmpeg version check
        mock_sub_run.return_value = MagicMock(returncode=0)
        
        # Prepare a downloaded item
        temp_file = os.path.join(self.context.temp_download_dir, "67890.mp4")
        with open(temp_file, 'wb') as f:
            f.write(b"video_data_here")
            
        item = {
            "ad_id": "67890",
            "media_type": "video",
            "status": "downloaded",
            "saved_path": temp_file,
            "app_name": "TestApp",
            "fpath": os.path.join(self.context.temp_download_dir, "67890.json")
        }
        self.context.items_db[item["fpath"]] = item
        self.context.filter_queue.put(item)
        
        # Run filter
        self.context.running = True
        t = threading.Thread(target=self.service.stream_3_dedup_filter)
        t.daemon = True
        t.start()
        
        time.sleep(0.5)
        self.context.running = False
        t.join(timeout=1.0)
        
        # Verify item state updated to done
        updated = self.context.items_db[item["fpath"]]
        self.assertEqual(updated["status"], "done")
        self.assertTrue(os.path.exists(updated["saved_path"]))
        print("✅ stream_3_dedup_filter unique mode verified successfully.")

    @patch('subprocess.run')
    def test_6_stream_3_dedup_filter_duplicate(self, mock_sub_run):
        """Test stream_3_dedup_filter when item is duplicate."""
        mock_sub_run.return_value = MagicMock(returncode=0)
        
        # Set deduplication to return duplicate
        self.context.deduplication_service.dup_results = {
            os.path.join(self.context.temp_download_dir, "duplicate_ad.mp4"): (True, "master_ad_id", "Layer 2: Audio PCM MD5 matches")
        }
        
        temp_file = os.path.join(self.context.temp_download_dir, "duplicate_ad.mp4")
        with open(temp_file, 'wb') as f:
            f.write(b"video_data_here")
            
        item = {
            "ad_id": "duplicate_ad",
            "media_type": "video",
            "status": "downloaded",
            "saved_path": temp_file,
            "app_name": "TestApp",
            "fpath": os.path.join(self.context.temp_download_dir, "duplicate_ad.json"),
            "youtube_url": "https://youtube.com/watch?v=xyz"
        }
        self.context.items_db[item["fpath"]] = item
        self.context.filter_queue.put(item)
        
        self.context.running = True
        t = threading.Thread(target=self.service.stream_3_dedup_filter)
        t.daemon = True
        t.start()
        
        time.sleep(0.5)
        self.context.running = False
        t.join(timeout=1.0)
        
        # Verify item state updated to duplicate
        updated = self.context.items_db[item["fpath"]]
        self.assertEqual(updated["status"], "duplicate")
        self.assertFalse(os.path.exists(temp_file))  # Temp file must be deleted
        self.assertIn("master_ad_id", self.context.session_service.master_urls) # Youtube url merged
        print("✅ stream_3_dedup_filter duplicate mode verified successfully.")

    def test_7_system_control_loop_and_lifecycle(self):
        """Test start_system, _system_control_loop, and stop_system."""
        # 1. Start system
        self.context.running = False
        self.service.start_system(thread_count=2)
        
        self.assertTrue(self.context.running)
        self.assertTrue(self.context.sys_monitor.started)
        self.assertEqual(len(self.service.download_threads), 2)
        self.assertTrue(self.service.dedup_thread.is_alive())
        self.assertTrue(self.service.monitor_control_thread.is_alive())
        
        # 2. Stop system
        self.service.stop_system()
        self.assertFalse(self.context.running)
        self.assertTrue(self.context.sys_monitor.stopped)
        print("✅ start_system, stop_system, _system_control_loop verified successfully.")

if __name__ == "__main__":
    unittest.main()
