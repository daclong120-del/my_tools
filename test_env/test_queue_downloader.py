import sys
import os
import unittest
import queue
import time
from unittest.mock import patch, MagicMock

# Add project root to python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "tools"))

from socialpeta_downloader.core import SocialPetaDownloaderCore

class TestQueueDownloader(unittest.TestCase):
    def setUp(self):
        # Mock settings to avoid configuration loading issues
        self.settings_patcher = patch('socialpeta_downloader.core.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.DOWNLOAD_DIR = "test_download_dir"
        self.mock_settings.SESSION_DIR = "test_session_dir"
        self.mock_settings.CHROME_DEBUG_PORT = 9222
        
        # Mock directory creations and system monitor
        self.makedirs_patcher = patch('os.makedirs')
        self.mock_makedirs = self.makedirs_patcher.start()
        
        self.sys_monitor_patcher = patch('socialpeta_downloader.core.SystemMonitor')
        self.mock_sys_monitor = self.sys_monitor_patcher.start()
        
        self.init_cache_patcher = patch('socialpeta_downloader.core.SocialPetaDownloaderCore._init_image_md5_cache')
        self.mock_init_cache = self.init_cache_patcher.start()

    def tearDown(self):
        self.settings_patcher.stop()
        self.makedirs_patcher.stop()
        self.sys_monitor_patcher.stop()
        self.init_cache_patcher.stop()

    def test_init_queue(self):
        core = SocialPetaDownloaderCore()
        self.assertTrue(hasattr(core, 'pending_downloads'), "core must have pending_downloads attribute")
        self.assertIsInstance(core.pending_downloads, queue.PriorityQueue, "pending_downloads must be a PriorityQueue")

    @patch('socialpeta_downloader.core.SocialPetaDownloaderCore._save_item_state')
    @patch('socialpeta_downloader.core.SocialPetaDownloaderCore.append_to_csv')
    @patch('socialpeta_downloader.core.SocialPetaDownloaderCore._is_ad_already_downloaded')
    @patch('socialpeta_downloader.core.SocialPetaDownloaderCore._read_temp_json')
    def test_process_api_response_enqueues(self, mock_read_temp, mock_is_downloaded, mock_append_csv, mock_save_state):
        mock_read_temp.return_value = {}
        mock_is_downloaded.return_value = False
        
        core = SocialPetaDownloaderCore()
        # Mock _parse_creative_item to return a pending video
        core._parse_creative_item = MagicMock(return_value={
            "ad_id": "test_ad_123",
            "media_type": "video",
            "video_url": "http://example.com/video.mp4",
            "fpath": "test_download_dir/.temp/api/test_ad_123.json"
        })
        core._recursive_find_creatives = MagicMock(return_value=[{"id": 1}])
        
        core.page_packet_received = MagicMock()
        
        # Execute processing
        core._process_api_response({"creatives": [{"id": 1}]})
        
        # Verify queue has the item
        self.assertFalse(core.pending_downloads.empty(), "PriorityQueue should not be empty")
        priority, fpath = core.pending_downloads.get_nowait()
        self.assertEqual(fpath, "test_download_dir/.temp/api/test_ad_123.json")

if __name__ == '__main__':
    unittest.main()
