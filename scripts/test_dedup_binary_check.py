# scripts/test_dedup_binary_check.py
import os
import sys
import unittest
import shutil
from unittest.mock import MagicMock, patch

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tools"))

from socialpeta_downloader.core import SocialPetaDownloaderCore

class TestDedupBinaryCheck(unittest.TestCase):
    def setUp(self):
        self.core = SocialPetaDownloaderCore()
        
    @patch('subprocess.run')
    def test_binaries_missing_graceful_bypass(self, mock_run):
        # Setup mock_run to raise FileNotFoundError when checking versions
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")
        
        # We can construct a mock item in filter_queue
        item = {
            "ad_id": "test_ad_123",
            "app_name": "TestGame",
            "saved_path": "test_temp_video.mp4"
        }
        
        # Create dummy file to simulate downloaded video
        with open("test_temp_video.mp4", "w") as f:
            f.write("dummy content")
            
        try:
            self.core.filter_queue.put(item)
            self.core.running = True
            
            original_get = self.core.filter_queue.get
            
            def mock_get(timeout=None):
                self.core.running = False  # Stop the loop after this get
                return original_get(timeout=timeout)
                
            self.core.filter_queue.get = mock_get
            
            # Run the filter
            self.core.downloader_service.stream_3_dedup_filter()
            
            # Now verify:
            # 1. The temp file was moved to the target directory
            # 2. Status in item became "done"
            # 3. dedup_checked is False, dedup_status is "chưa kiểm tra trùng lặp"
            self.assertEqual(item["status"], "done")
            self.assertFalse(item["dedup_checked"])
            self.assertEqual(item["dedup_status"], "chưa kiểm tra trùng lặp")
            
            # Verify target file exists
            saved_path = item["saved_path"]
            self.assertTrue(os.path.exists(saved_path))
            
            # Clean up target file
            if os.path.exists(saved_path):
                os.remove(saved_path)
                
        finally:
            if os.path.exists("test_temp_video.mp4"):
                os.remove("test_temp_video.mp4")

if __name__ == '__main__':
    unittest.main()
