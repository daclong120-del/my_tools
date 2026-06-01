# scripts/test_core_split.py
import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tools"))

from socialpeta_downloader.core import SocialPetaDownloaderCore

class TestCoreSplit(unittest.TestCase):
    def setUp(self):
        self.core = SocialPetaDownloaderCore()

    def test_mixins_presence(self):
        # Check that methods from different mixins are available on core
        # UtilsMixin
        self.assertTrue(hasattr(self.core, 'clean_app_name'))
        self.assertTrue(hasattr(self.core, 'get_unique_filename'))
        self.assertTrue(hasattr(self.core, 'append_to_csv'))
        
        # ChromeMixin
        self.assertTrue(hasattr(self.core, 'ensure_chrome_debug_port'))
        self.assertTrue(hasattr(self.core, 'check_and_launch_chrome'))
        
        # DedupMixin
        self.assertTrue(hasattr(self.core, 'check_duplicate'))
        self.assertTrue(hasattr(self.core, 'get_video_duration'))
        
        # SnifferMixin
        self.assertTrue(hasattr(self.core, 'stream_1_sniffer'))
        
        # TabManagerMixin
        self.assertTrue(hasattr(self.core, 'run_tab_scraper'))
        self.assertTrue(hasattr(self.core, 'detect_tabs'))
        
        # DownloaderMixin
        self.assertTrue(hasattr(self.core, '_download_worker'))
        self.assertTrue(hasattr(self.core, 'start_system'))
        self.assertTrue(hasattr(self.core, 'stop_system'))
        
        # YoutubeMixin
        self.assertTrue(hasattr(self.core, '_youtube_extract_worker'))
        
        # LegacySnifferMixin
        self.assertTrue(hasattr(self.core, 'stream_1_sniffer'))
        
        # LegacyScraperMixin
        self.assertTrue(hasattr(self.core, 'download_single_ad'))
        self.assertTrue(hasattr(self.core, 'scrape_search_page_and_download'))

    def test_clean_app_name(self):
        self.assertEqual(self.core.clean_app_name("My Cool Game - Fun Action"), "MyCool")
        self.assertEqual(self.core.clean_app_name("Rise of Kingdoms: Lost Crusade"), "RiseOf")
        self.assertEqual(self.core.clean_app_name("Candy Crush Saga | Match 3"), "CandyCrush")
        self.assertEqual(self.core.clean_app_name("SimpleApp"), "SimpleApp")

    def test_get_unique_filename(self):
        filename, stt = self.core.get_unique_filename("Test App")
        self.assertTrue(filename.startswith("Test_SPY_"))
        self.assertTrue(filename.endswith(".mp4"))
        self.assertGreater(stt, 0)

    def test_get_unique_image_filename(self):
        filename, stt = self.core.get_unique_image_filename("Test App", "https://example.com/path/to/img.png?size=large")
        self.assertTrue(filename.startswith("Test_SPY_"))
        self.assertTrue(filename.endswith(".png"))
        self.assertGreater(stt, 0)

if __name__ == '__main__':
    unittest.main()
